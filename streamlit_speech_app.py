import streamlit as st
import requests
import uuid
import os
import io
import time
from audio_recorder_streamlit import audio_recorder

# Configure the base URL for your FastAPI backend
BASE_URL = "https://testing.murshed.marahel.sa/"
# BASE_URL = "http://127.0.0.1:9696/"

def get_speech_to_text(audio_bytes):
    """Convert speech to text using the API"""
    try:
        files = {'file': ('audio.wav', audio_bytes, 'audio/wav')}
        response = requests.post(f"{BASE_URL}/api/speech-to-text", files=files)
        if response.status_code == 200:
            return response.json()['data']['response']
        return None
    except Exception as e:
        st.error(f"Error in speech to text conversion: {str(e)}")
        return None

def get_text_to_speech(text, voice_type):
    """Convert text to speech using the API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/text-to-speech",
            json={"text": text, "voice_type": voice_type},
            stream=True
        )
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        st.error(f"Error in text to speech conversion: {str(e)}")
        return None

def get_playht_text_to_speech(text):
    """Convert text to speech using the PlayHT API"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/playht-text-to-speech",
            json={"text": text},
            stream=True
        )
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        st.error(f"Error in PlayHT text to speech conversion: {str(e)}")
        return None

def main():
    # Hard-coded parameters
    llm_model = "openai"
    embeddings_model = "openai"
    vectorstore_database = "qdrant"
    chunk_size = 1000
    chunk_overlap = 100

    # Title / Welcome message
    st.title("Welcome To The Murshad")

    # Initialize session state variables
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "chatbot_id" not in st.session_state:
        st.session_state.chatbot_id = str(uuid.uuid4())
    if "user_id" not in st.session_state:
        st.session_state.user_id = str(uuid.uuid4())
    if "document_processed" not in st.session_state:
        st.session_state.document_processed = False
    if "processing_error" not in st.session_state:
        st.session_state.processing_error = False
    if "audio_bytes" not in st.session_state:
        st.session_state.audio_bytes = None
    if "last_audio_bytes" not in st.session_state:
        st.session_state.last_audio_bytes = None
    if "is_processing_audio" not in st.session_state:
        st.session_state.is_processing_audio = False
    if "voice_type" not in st.session_state:
        st.session_state.voice_type = "alloy"  # Default voice type
    if "tts_provider" not in st.session_state:
        st.session_state.tts_provider = "openai"  # Default to OpenAI

    # ----- SIDEBAR -----
    with st.sidebar:
        st.header("Configuration")
        st.info(f"Chatbot ID: {st.session_state.chatbot_id}")
        st.info(f"User ID: {st.session_state.user_id}")

        # TTS Provider selection
        st.session_state.tts_provider = st.radio(
            "Select TTS Provider",
            options=["openai", "playht"],
            index=0 if st.session_state.tts_provider == "openai" else 1
        )

        # Voice type selection (only show for OpenAI)
        if st.session_state.tts_provider == "openai":
            voice_options = ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]
            st.session_state.voice_type = st.selectbox(
                "Select Voice Type",
                options=voice_options,
                index=voice_options.index(st.session_state.voice_type)
            )

        # Document Upload (only PDF)
        st.subheader("Document Upload (PDF only)")
        uploaded_files = st.file_uploader(
            "Upload PDF Documents",
            accept_multiple_files=True,
            type=["pdf"]
        )

        # Validate uploaded files
        valid_pdf_files = []
        if uploaded_files:
            for file in uploaded_files:
                if file.name.lower().endswith('.pdf'):
                    valid_pdf_files.append(file)
                else:
                    st.warning(f"'{file.name}' is not a PDF. Please upload PDF files only.")

        # Process button
        if st.button("Process Documents"):
            st.session_state.processing_error = False
            if not valid_pdf_files:
                st.warning("No valid PDF files to process.")
            else:
                with st.spinner("Processing documents..."):
                    try:
                        files = [
                            ('files', (file.name, file.read(), file.type))
                            for file in valid_pdf_files
                        ]

                        form_data = {
                            "chatbot_id": st.session_state.chatbot_id,
                            "chunk_size": str(chunk_size),
                            "chunk_overlap": str(chunk_overlap),
                            "embeddings_model": embeddings_model,
                            "vectorstore_name": vectorstore_database,
                            "llm": llm_model
                        }

                        response = requests.post(
                            f"{BASE_URL}/api/Ingestion_File",
                            files=files,
                            data=form_data
                        )

                        if response.status_code == 200:
                            st.success("PDF(s) processed successfully!")
                            st.session_state.document_processed = True
                            st.session_state.chat_history = []  # Reset chat history for new documents
                        else:
                            st.session_state.processing_error = True
                            st.error(f"Error: {response.json().get('message', 'Unknown error occurred')}")
                    except Exception as e:
                        st.session_state.processing_error = True
                        st.error(f"Error processing documents: {str(e)}")

    # ---- MAIN INTERFACE ----
    if not st.session_state.document_processed or st.session_state.processing_error:
        st.info("Please upload and process at least one PDF file to start chatting.")
        return

    # Display chat history
    for idx, message in enumerate(st.session_state.chat_history):
        with st.chat_message(message["role"]):
            content = message["content"]
            
            if message["role"] == "assistant":
                # Display response text immediately
                st.write(content["response"])
                
                # Generate audio in background if not already present
                if "audio" not in content:
                    with st.spinner("Generating audio response..."):
                        if st.session_state.tts_provider == "openai":
                            content["audio"] = get_text_to_speech(
                                content["response"],
                                st.session_state.voice_type
                            )
                        else:  # playht
                            content["audio"] = get_playht_text_to_speech(
                                content["response"]
                            )
                        # Update the message in chat history with audio
                        st.session_state.chat_history[idx]["content"] = content
                
                # Display audio player and download button if audio is available
                if content.get("audio"):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.audio(content["audio"], format='audio/mp3')
                    with col2:
                        # Generate a unique filename for each audio response
                        filename = f"murshad_response_{idx}.mp3"
                        st.download_button(
                            label="💾 Download",
                            data=content["audio"],
                            file_name=filename,
                            mime="audio/mp3"
                        )
                
                # Display sources if available
                if "source" in content:
                    with st.expander("View Sources"):
                        for source in content["source"]:
                            st.write(f"Document: {source['documents']['filename']}")
                            st.write(f"Pages: {', '.join(map(str, source['documents']['pages']))}")
            else:
                st.write(content)

    # Simple input section without columns
    prompt = st.chat_input("Type or speak your question")
    
    # Audio recorder
    audio_bytes = audio_recorder(
        pause_threshold=2.0,
        sample_rate=44100,
        key="audio_recorder"
    )
    
    # Only process new audio if we're not already processing
    if (audio_bytes and 
        not st.session_state.is_processing_audio and 
        audio_bytes != st.session_state.get('last_audio_bytes')):
        
        st.session_state.is_processing_audio = True
        with st.spinner("Converting speech to text..."):
            text_from_speech = get_speech_to_text(audio_bytes)
            if text_from_speech:
                st.info(f"Recognized: {text_from_speech}")
                prompt = text_from_speech
                st.session_state.last_audio_bytes = audio_bytes
        
        st.session_state.is_processing_audio = False

    # Process text input (from either typing or speech)
    if prompt and not st.session_state.is_processing_audio:
        # Show user's message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Get AI response
        with st.spinner("Generating response..."):
            try:
                response = requests.post(
                    f"{BASE_URL}/api/chat-bot",
                    json={
                        "query": prompt,
                        "chatbot_id": st.session_state.chatbot_id,
                        "user_id": st.session_state.user_id
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    ai_response = response.json()["data"]
                    # First add the response without audio
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": ai_response
                    })
                    # Rerun to show the text response immediately
                    st.rerun()
                else:
                    st.error(f"API Error: {response.json().get('message', 'Unknown error occurred')}")
            except requests.exceptions.Timeout:
                st.error("Request timed out. Please try again.")
            except Exception as e:
                st.error(f"Error getting response: {str(e)}")

if __name__ == "__main__":
    main()