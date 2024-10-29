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
Please analyze the provided construction plan document and compile a comprehensive report detailing the square footage for the following materials and components:

1. Sheetrock
2. Concrete
3. Roofing

For roofing, provide a breakdown for each subtype:
   - Shingle roofing
   - Modified bitumen
   - TPO (Thermoplastic Polyolefin)
   - Metal R panel
   - Standing seam

4. Structural steel

The construction document may contain multiple sections and phases. Ensure that the square footage calculations are complete, accounting for all relevant parts and subparts of the document. If there are multiple entries for a particular material, sum them to provide a total square footage.

Additionally, include a concise summary of the construction plan, outlining the key details such as:
   - Materials specified
   - Construction phases covered
   - Notable specifications or design considerations

The final report should follow this structured format:

{
    "Sheetrock": {
        "total_square_footage": <value>,
        "details": "<description or any relevant notes>"
    },
    "Concrete": {
        "total_square_footage": <value>,
        "details": "<description or any relevant notes>"
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
        "details": "<description or any relevant notes>"
    },
    "Structural steel": {
        "total_square_footage": <value>,
        "details": "<description or any relevant notes>"
    },
    "Plan Summary": {
        "Overview": "<brief summary of the overall plan>",
        "Materials": "<list of key materials>",
        "Phases": "<list of construction phases covered>",
        "Specifications": "<important design or construction specifications>"
    }
}

Ensure the report is detailed, accurate, and provides a complete overview of the square footage calculations and essential aspects of the construction plan.
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

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])
if uploaded_file:
    first_response = client.chat.completions.create(
        model="gpt-4o",  # or the model you're using
        messages=[{"role": "user", "content": f"take this as instruction and say 'i am ready! how can i help you.' if you are ready.{first_query}"}]
    )
    if first_response.choices and len(first_response.choices) > 0:
        first_generated_response = first_response.choices[0].message.content
   

    with st.chat_message('assistant'):
        st.markdown(first_generated_response)


# Initialize session state to manage chat interaction
if 'responses' not in st.session_state:
    st.session_state.responses = []
if 'encoded_images' not in st.session_state:
    st.session_state.encoded_images = []
if 'current_query' not in st.session_state:
    st.session_state.current_query = ""

# Chat interaction
if uploaded_file and api_key:
    # Create a temporary directory for image storage
    with tempfile.TemporaryDirectory() as temp_dir:
        RESULTS_PATH = temp_dir
        
        # Convert uploaded PDF to images
        pdf_to_images(uploaded_file, RESULTS_PATH)

        # Encode images to Base64
        st.session_state.encoded_images = encode_images(RESULTS_PATH)
        
        # Save to JSON (optional, depending on your use case)
        json_file_path = 'encoded_images.json'
        save_to_json(st.session_state.encoded_images, json_file_path)

        for message in st.session_state.responses:
            with st.chat_message(message['role']):
                st.markdown(message['content'])

        # User input for the query
        if st.session_state.current_query == "":
            if user_query := st.chat_input("Enter your query:"):
                if user_query:  # Check if the user has entered a query
                    st.session_state.current_query = user_query  # Store current query
                    st.session_state.responses.append({"role":"user","content": user_query})  # Store user query
                    with st.spinner("Analyzing data..."):
                        # Get the combined streamed response
                        response = chunk_api_requests(st.session_state.encoded_images, user_query, api_key)

                    with st.chat_message('user'):
                        st.markdown(user_query)
                    # Stream the final response
                    with st.chat_message('assistant'):
                        st.markdown(response)
                    st.session_state.responses.append({"role":"assistant","content": response})  # Store bot response
                    st.session_state.current_query = ""  # Reset current query for next input
        else:
            st.warning("Please complete your current query before sending another.")
else:
    st.warning("Please upload a PDF.")
