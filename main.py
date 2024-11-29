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

    # Prepare the initial system message to maintain context (Will be changed if needed)
    system_prompt = {
        "role": "system",
        "content": """
                You are an intelligent construction assistant that analyzes construction plans. Give numarical answers for the user query, do not guess or provide irrelevant information.
                Include:       
                - Values with context that matches the user query.        
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

            answer = f'Chatbot Created by Digimark Developers. {response.choices[0].message.content}'
            all_responses.append(answer)
            progress = (i + 1) / len(encoded_images)  # Calculate progress as a fraction
            progress_bar.progress(progress, text='Analyzing Complete data, please wait ...')
        except:
            print('Error, Moving to Next')
            
        st.session_state.all_query_responses.append(all_responses)


# Function to get top 10 most similar results using FuzzyWuzzy
def get_top_similar_results(input_query, sections):
    # Use FuzzyWuzzy to find the top 10 matches
    results = process.extract(input_query, sections, limit=10, scorer=fuzz.ratio)
    top_results = [result[0] for result in results]
    return top_results

# Main function to process the query and text file and get response
def get_similarity_response( input_query):
    text = st.session_state.all_query_responses
    string_text = str(text)
    
    # Split the text into sections based on the pattern
    split_pattern = r"Chatbot Created by Digimark Developers. "
    sections = re.split(split_pattern, string_text)
    
    print('sections', sections)
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
        stream=True,
    )

    streamed_content = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            streamed_content += chunk.choices[0].delta.content

    return streamed_content