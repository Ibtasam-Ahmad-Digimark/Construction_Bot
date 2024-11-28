import os
import fitz  # PyMuPDF
import base64
import json
import requests
import time
import streamlit as st
import tempfile  
import re
import json


from dotenv import load_dotenv
from openai import OpenAI
from fuzzywuzzy import fuzz
from fuzzywuzzy import process


api_key=st.secrets["OPENAI_API_KEY"]
# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])





first_query = """
Please analyze the provided construction plan document and return every numerical square footage values for the following materials and components:

1. **Sheetrock:** (e.g., square footage or dimensions)
2. **Concrete:** (e.g., square footage or dimensions)
3. **Roofing:** Break down by subtype: (e.g., square footage or dimensions)
   - Shingle roofing
   - Modified bitumen
   - TPO (Thermoplastic Polyolefin)
   - Metal R-panel
   - Standing seam
4. **Structural Steel:** (e.g., square footage or dimensions)

Also give all the possible details you can extract from the data. Make sure the word count should be less than 700
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

# Function to make chunked API requests and stream combined responses
def chunk_api_requests(encoded_images, user_query, api_key):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    all_responses = []

    # Prepare the initial system message to maintain context
    system_prompt = {
        "role": "system",
        "content": """
                You are an intelligent construction assistant that analyzes construction plans. Give numarical answers for the user query, do not guess or provide irrelevant information. Only include:       
                - Values with context that matches the user query (e.g., square footage or dimensions).        
                - Brief and accurate summaries directly tied to the document's content.         
                If specific data is not available, state that it is unavailable in the document.
            """
        }

    # Prepare the conversation history
    messages = [system_prompt]  # Start with the system message
    messages.extend(st.session_state.responses)  # Add previous chats
    messages.append({"role": "user", "content": user_query})  # Add current user query


    all_responses = []
    progress_bar = st.progress(0)

    for i in range(0, len(encoded_images)):
        time.sleep(10)
        try:
            response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                "role": "user",
                "content": [
                    {
                    "type": "text",
                    "text": user_query,
                    },
                    {
                    "type": "image_url",
                    "image_url": {
                        "url":  f"data:image/jpeg;base64,{encoded_images[i]}"
                    },
                    },
                ],
                }
            ],
            )

            answer = response.choices[0].message.content
            all_responses.append(answer)
            progress = (i + 1) / len(encoded_images)  # Calculate progress as a fraction
            progress_bar.progress(progress, text='Analyzing Complete data, please wait ...')
        except:
            print('Error, Moving to Next')

        st.session_state.all_query_responses.append(all_responses)

    # Stream the combined response
    streamed_content = response_from_gpt(user_query,all_responses)

    return streamed_content

# Function to read the text file and extract the content
def read_txt_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            text = file.read()
    except UnicodeDecodeError:
        # If utf-8 fails, try opening with 'latin-1' encoding
        with open(file_path, 'r', encoding='latin-1') as file:
            text = file.read()
    return text

# Function to split the text based on "The response for"
def split_text(text):
    # This regular expression will match the pattern "The response for"
    string_text = str(text)
    split_pattern = r"The response for (\d+th image is)"
    # Split the text into sections based on the pattern
    sections = re.split(split_pattern, string_text)
    return [section.strip() for section in sections if section.strip()]

# Function to get top 5 most similar results using FuzzyWuzzy
def get_top_similar_results(input_query, sections):
    # Use FuzzyWuzzy to find the top 5 matches
    results = process.extract(input_query, sections, limit=5, scorer=fuzz.ratio)
    top_results = [result[0] for result in results]
    return top_results

# Main function to process the query and text file and get response
def get_similarity_response( input_query):
    # Step 1: Read the content of the text file
    text = st.session_state.all_query_responses
    
    # Step 2: Split the text into sections
    sections = split_text(text)
    
    # Step 3: Get the top 5 most similar results using FuzzyWuzzy
    top_results = get_top_similar_results(input_query, sections)
    return top_results

# Function for the response from the gpt by all responses
def response_from_gpt(user_query, all_responses):
    
    stream = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": f'''Given the following user query and multiple responses, identify and combine the most relevant portions of the responses to provide a comprehensive and informative answer:

        **User Query:**
        {user_query}

        **Multiple Responses:**
        {all_responses}

        **Guidelines:**
        * Prioritize accuracy and relevance to the user's query.
        * Combine information from multiple responses if necessary.
        * Avoid redundancy and repetition.
        * Present the information in a clear and concise manner.

        **Output:**
        A single, coherent response that addresses the user's query effectively.
        '''}],
        # stream=True,
    )

    streamed_content = stream.choices[0].message
    # streamed_content = ""
    # for chunk in stream:
    #     if chunk.choices[0].delta.content is not None:
    #         streamed_content += chunk.choices[0].delta.content

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
if 'all_query_responses' not in st.session_state:
    st.session_state.all_query_responses = []


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

    for message in st.session_state.responses:
        with st.chat_message(message['role']):
            st.markdown(message['content'])

    # First predefined query logic
    if st.session_state.is_first_query:
        user_query = first_query
        st.session_state.current_query = user_query

        with st.spinner("Analyzing Complete Data..."):
            # Get the combined streamed response
            _f_response = chunk_api_requests(st.session_state.encoded_images, user_query, api_key)

        with st.chat_message('assistant'):
            st.markdown(_f_response)
        st.session_state.responses.append({"role": "assistant", "content": _f_response})

        st.session_state.is_first_query = False  # After processing the first query
        st.session_state.current_query = ""  # Clear current query after first completion

    # Display chat_input after first query
    col1, col2 = st.columns([3, 1])  # Adjust the column widths as needed

    # Display the chat input in the first column
    with col1:
        user_query = st.chat_input("Enter your query:")

    # Display the radio button in the second column
    with col2:
        deep_analysis_option = st.toggle("Deep Analysis", value=False)
        # deep_analysis_option = st.radio("Choose an option:", ["On", "Off"], index=1)
    if user_query:

        # Save user query to session state for reference
        st.session_state.responses.append({"role": "user", "content": user_query})

        if deep_analysis_option:
            print('aple')
            with st.spinner("Deeply Analyzing Data..."):
                response = chunk_api_requests(st.session_state.encoded_images, user_query, api_key)

            # Display the deep analysis response
            with st.chat_message('assistant'):
                st.markdown(response)
            
            # Append the new deep analysis response to session state
            st.session_state.responses.append({"role": "assistant", "content": response})

        else:
        # Initial response generation
            with st.spinner("Analyzing data..."):
                # Generate similarity response based on the user's query
                top_response = get_similarity_response(user_query)
                response = response_from_gpt(user_query, top_response)
            
            # Display the user's query and the initial assistant response
                with st.chat_message('user'):
                    st.markdown(user_query)

                with st.chat_message('assistant'):
                    st.markdown(response)
                
                # Store the assistant response in session state for future use
                st.session_state.responses.append({"role": "assistant", "content": response})

else:
    # If no user query is provided, show a warning about the PDF upload
    st.warning("Please upload a PDF. Uploading PDF an deep Anaysis might take some time; don't close the application.")
