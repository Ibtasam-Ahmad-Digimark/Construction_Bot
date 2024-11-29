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

from main import pdf_to_images, encode_images, chunk_api_requests, get_similarity_response, response_from_gpt


api_key=st.secrets["OPENAI_API_KEY"]
# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])



intitial_prompt = """
Please analyze the provided construction plan and return every numerical square footage values for the following materials and components:

1. **Sheetrock:** 
2. **Concrete:** 
3. **Roofing:** Break down by subtype: 
   - Shingle roofing
   - Modified bitumen
   - TPO (Thermoplastic Polyolefin)
   - Metal R-panel
   - Standing seam
4. **Structural Steel:** 

If you don't find any of these, don't write anything about it .Don't say 'No specific numerical values or references have been listed for **Sheetrock**, **Structural Steel**, or distinct types of **Roofing** materials like Shingle Roofing, Modified Bitumen, TPO, Metal R-panel, and Standing Seam in the visible parts of the construction plan' or any thing about this.


Extract all the possible details you can extract from the data, ensuring that each type of information is formatted in separate paragraphs. For each category, summarize the relevant information in a single paragraph. Ensure all numerical values, quantities, and other detailed information are included, such as measurements, dates, labels, or any other figures present, with each paragraph corresponding to a different type of detail from the data. The paragraphs should be as detailed as possible, reflecting the contents of the image with clarity. 
"""


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

Also give all the possible details you can extract from the data.
"""



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
        user_query = intitial_prompt
        st.session_state.current_query = user_query

        with st.spinner("Analyzing Complete Data..."):

            # Get the combined streamed response
            chunk_api_requests(st.session_state.encoded_images, user_query, api_key)
            top_response = get_similarity_response(first_query)
            _f_response = response_from_gpt(user_query, top_response)


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
            with st.spinner("Deeply Analyzing Data..."):
                chunk_api_requests(st.session_state.encoded_images, user_query, api_key)
                top_response = get_similarity_response(first_query)
                d_response = response_from_gpt(user_query, top_response)

            # Display the deep analysis response
            with st.chat_message('assistant'):
                st.markdown(d_response)
            
            # Append the new deep analysis response to session state
            st.session_state.responses.append({"role": "assistant", "content": d_response})

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
