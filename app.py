import os
import fitz  # PyMuPDF
import base64
import json
import requests
import time
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
import tempfile  # Import tempfile for temporary directories
api_key=st.secrets["OPENAI_API_KEY"]
# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


first_query = """
Please review the provided construction plan document and prepare a comprehensive report that captures the square footage for the following materials and components:

1. Sheetrock
2. Concrete
3. Roofing

For roofing, kindly break down the details for each subtype:
   - Shingle roofing
   - Modified bitumen
   - TPO (Thermoplastic Polyolefin)
   - Metal R panel
   - Standing seam

4. Structural steel

The construction plan may consist of multiple sections or phases. Please make sure the square footage calculations are thorough and include all relevant areas of the document. If there are multiple entries for any material, please combine them to present a total square footage.

Along with the square footage, it would be helpful to include a brief, thoughtful summary of the overall construction plan, highlighting key aspects such as:
   - Materials used
   - Phases of construction outlined
   - Any noteworthy specifications or design elements

The report should be formatted as follows:

{
    "Sheetrock": {
        "total_square_footage": <value>,
        "details": "<any additional notes or observations>"
    },
    "Concrete": {
        "total_square_footage": <value>,
        "details": "<any additional notes or observations>"
    },
    "Roofing": {
        "total_square_footage": <value>,
        "subtypes": {
            "Shingle roofing": <value>,
            "Modified bitumen": <value>,
            "TPO": <value>,
            "Metal R panel": <value>,
            "Standing seam": <value>
        },
        "details": "<any additional notes or observations>"
    },
    "Structural steel": {
        "total_square_footage": <value>,
        "details": "<any additional notes or observations>"
    },
    "Plan Summary": {
        "Overview": "<a thoughtful summary of the overall plan>",
        "Materials": "<key materials highlighted in the plan>",
        "Phases": "<construction phases and timelines>",
        "Specifications": "<any important design considerations>"
    }
}

Please approach this task with a focus on clarity and completeness, and feel free to add any helpful insights that may assist in understanding the scope and details of the plan. The goal is to provide a report that not only delivers the numbers but also tells the story of the project in a clear and approachable way.
"""

# Function to convert PDF to images
def pdf_to_images(uploaded_file, output_dir):
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    for i in range(len(pdf_document)):
        page = pdf_document.load_page(i)
        pix = page.get_pixmap()
        img_path = os.path.join(output_dir, f'page_{i}.jpg')
        pix.save(img_path)
    pdf_document.close()

# Function to encode images to Base64
def encode_images(image_directory):
    encoded_images = []
    for filename in os.listdir(image_directory):
        if filename.lower().endswith((".png", ".jpg", ".jpeg")):
            image_path = os.path.join(image_directory, filename)
            with open(image_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
                encoded_images.append(encoded_image)
    return encoded_images

# Function to save encoded images to JSON
def save_to_json(encoded_images, json_path):
    with open(json_path, 'w') as json_file:
        json.dump(encoded_images, json_file)

# Function to load encoded images from JSON
def load_from_json(json_path):
    with open(json_path, 'r') as json_file:
        return json.load(json_file)

# Function to make chunked API requests and stream combined responses
def chunk_api_requests(encoded_images, user_query, api_key):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    chunk_size = 17
    all_responses = []

    for i in range(0, len(encoded_images), chunk_size):
        time.sleep(1)  # Simulating a delay
        chunk = encoded_images[i:i + chunk_size]
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [user_query] + [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img}"
                            }
                        } for img in chunk
                    ]
                }
            ],
            "max_tokens": 3000
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        
        try:
            response_content = response.json()['choices'][0]['message']['content']
            all_responses.append(response_content)
        except Exception as e:
            all_responses.append(f"Error: {str(e)}")

    # Combine all responses into a single message
    combined_responses = "\n\n".join(all_responses)

    # Stream the combined response
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f'Combine all the responses and explain it as one response: {combined_responses}'}],
        stream=True,
    )

    streamed_content = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            streamed_content += chunk.choices[0].delta.content

    return streamed_content

# Streamlit UI
st.title("PDF Chatbot")

uploaded_file = st.file_uploader("Upload a PDF.", type=["pdf"])

# Initialize session state to manage chat interaction
if 'responses' not in st.session_state:
    st.session_state.responses = []
if 'encoded_images' not in st.session_state:
    st.session_state.encoded_images = []
if 'current_query' not in st.session_state:
    st.session_state.current_query = ""
if 'is_first_query' not in st.session_state:
    st.session_state.is_first_query = True  # Track if it's the first query

# Chat interaction
if uploaded_file and api_key:
    # Only process the PDF if it hasn't been processed yet
    if not st.session_state.encoded_images:
        with tempfile.TemporaryDirectory() as temp_dir:
            RESULTS_PATH = temp_dir
            
            with st.spinner("Uploading PDF..."):
                # Convert uploaded PDF to images and encode only once
                pdf_to_images(uploaded_file, RESULTS_PATH)
                st.session_state.encoded_images = encode_images(RESULTS_PATH)
                
                # Optional: Save to JSON, if needed
                json_file_path = 'encoded_images.json'
                save_to_json(st.session_state.encoded_images, json_file_path)

    for message in st.session_state.responses:
        with st.chat_message(message['role']):
            st.markdown(message['content'])

    # First predefined query logic
    if st.session_state.is_first_query:
        user_query = first_query
        st.session_state.current_query = user_query

        with st.spinner("Analyzing data..."):
            # Get the combined streamed response
            _f_response = chunk_api_requests(st.session_state.encoded_images, user_query, api_key)

        with st.chat_message('assistant'):
            st.markdown(_f_response)
        st.session_state.responses.append({"role": "assistant", "content": _f_response})

        st.session_state.is_first_query = False  # After processing the first query
        st.session_state.current_query = ""  # Clear current query after first completion

    # Display chat_input after first query
    # user_query = 
    if user_query:=st.chat_input("Enter your query:"):
        st.session_state.responses.append({"role": "user", "content": user_query})
        with st.spinner("Analyzing data..."):
            # Process user input and provide response
            response = chunk_api_requests(st.session_state.encoded_images, user_query, api_key)

        with st.chat_message('user'):
            st.markdown(user_query)

        with st.chat_message('assistant'):
            st.markdown(response)
        st.session_state.responses.append({"role": "assistant", "content": response})
else:
    st.warning("Please upload a PDF. Uploading PDF might take some time; don't close the application.")
