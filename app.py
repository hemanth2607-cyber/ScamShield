import streamlit as st
import os
import re
import math
import speech_recognition as sr

TRAINING_DATA = [
    ("This is the IRS, you owe back taxes and will be arrested", "scam"),
    ("Your bank account is compromised, send money to the secure vault", "scam"),
    ("Congratulations, you won a free gift card, click here or call us", "scam"),
    ("This is Microsoft support, your computer has a virus, download this link", "scam"),
    ("Your grandson is in jail and needs bail money immediately", "scam"),
    ("Urgent: Pay your utility bill now or we will shut off your electricity", "scam"),
    ("Verify your social security number to avoid immediate suspension", "scam"),
    ("Send bitcoin to unlock your locked bank account", "scam"),
    
    ("Hey grandma, are we still meeting for lunch tomorrow at twelve", "safe"),
    ("Your dentist appointment is scheduled for Tuesday at three PM", "safe"),
    ("Hi, I am calling from the library, your book is ready for pickup", "safe"),
    ("Did you see the weather forecast for this weekend? It looks like rain", "safe"),
    ("Hey, I left my keys at your house, can I come by to get them", "safe"),
    ("The package you ordered yesterday has been delivered to your porch", "safe"),
    ("Hi, this is mom, just calling to check in and see how you are doing", "safe"),
    ("Your prescription is ready for pickup at the local pharmacy", "safe")
]

class NaiveBayesScamDetector:
    def __init__(self):
        self.scam_word_counts = {}
        self.safe_word_counts = {}
        self.total_scam_words = 0
        self.total_safe_words = 0
        self.num_scam_docs = 0
        self.num_safe_docs = 0
        self.unique_words = set()

    def _tokenize(self, text):
        text = text.lower()
        words = re.findall(r'\b\w+\b', text)
        return words

    def train(self, dataset):
        for text, label in dataset:
            words = self._tokenize(text)
            if label == "scam":
                self.num_scam_docs += 1
                for word in words:
                    self.scam_word_counts[word] = self.scam_word_counts.get(word, 0) + 1
                    self.total_scam_words += 1
                    self.unique_words.add(word)
            elif label == "safe":
                self.num_safe_docs += 1
                for word in words:
                    self.safe_word_counts[word] = self.safe_word_counts.get(word, 0) + 1
                    self.total_safe_words += 1
                    self.unique_words.add(word)

    def predict(self, text):
        words = self._tokenize(text)
        total_docs = self.num_scam_docs + self.num_safe_docs
        
        if total_docs == 0:
            return "safe", 0.5
            
        p_scam_log = math.log(self.num_scam_docs / total_docs)
        p_safe_log = math.log(self.num_safe_docs / total_docs)
        vocabulary_size = len(self.unique_words)

        for word in words:
            scam_word_count = self.scam_word_counts.get(word, 0)
            p_word_given_scam = (scam_word_count + 1) / (self.total_scam_words + vocabulary_size)
            p_scam_log += math.log(p_word_given_scam)

            safe_word_count = self.safe_word_counts.get(word, 0)
            p_word_given_safe = (safe_word_count + 1) / (self.total_safe_words + vocabulary_size)
            p_safe_log += math.log(p_word_given_safe)

        max_log = max(p_scam_log, p_safe_log)
        prob_scam_raw = math.exp(p_scam_log - max_log)
        prob_safe_raw = math.exp(p_safe_log - max_log)
        
        sum_raw = prob_scam_raw + prob_safe_raw
        final_scam_prob = prob_scam_raw / sum_raw

        if final_scam_prob > 0.5:
            return "scam", final_scam_prob
        else:
            return "safe", (1 - final_scam_prob)

@st.cache_resource
def get_trained_detector():
    detector = NaiveBayesScamDetector()
    detector.train(TRAINING_DATA)
    return detector

detector = get_trained_detector()

st.set_page_config(page_title="Scam Shield", page_icon="🛡️", layout="centered")
st.title("🛡️ Scam Shield Portal")
st.write("A privacy-first, zero-cloud detection system protecting vulnerable individuals from telephone fraud.")

tab1, tab2 = st.tabs(["🎙️ Audio File Analysis", "✍️ Manual Text / SMS Analysis"])

with tab1:
    st.header("Analyze Call Audio")
    uploaded_file = st.file_uploader("Choose a WAV file", type=["wav"])
    
    if uploaded_file is not None:
        temp_filename = "temp_uploaded_call.wav"
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        st.audio(uploaded_file, format="audio/wav")
        
        with st.spinner("Processing speech-to-text..."):
            recognizer = sr.Recognizer()
            try:
                with sr.AudioFile(temp_filename) as source:
                    audio_data = recognizer.record(source)
                    transcribed_text = recognizer.recognize_google(audio_data)
                    
                st.success("Transcription Complete!")
                st.text_area("Intercepted Transcript:", value=transcribed_text, height=100, disabled=True)
                
                classification, confidence = detector.predict(transcribed_text)
                if classification == "scam" and confidence > 0.60:
                    st.error(f"⚠️ HIGH SCAM RISK DETECTED ({confidence:.2%})")
                    st.warning("ACTION ADVISED: Hang up immediately.")
                else:
                    st.success(f"✅ Call segment appears safe ({confidence:.2%} confidence)")
            except Exception as e:
                st.error(f"Error: {e}")
            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

with tab2:
    st.header("Analyze Text Messages")
    user_input = st.text_area("Input message here:")
    if st.button("Run Text Analysis"):
        if user_input.strip() != "":
            classification, confidence = detector.predict(user_input)
            if classification == "scam" and confidence > 0.60:
                st.error(f"🚨 SCAM THREAT FLAGGED ({confidence:.2%})")
            else:
                st.success(f"🟢 SAFE / LOW RISK ({confidence:.2%})")
