# -*- coding: utf-8 -*-
"""
Created on Mon Mar 31 23:51:25 2025

@author: jtste
"""

from transformers import pipeline

# Load summarization model with GPU acceleration
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")  # 'device=0' for GPU

# Example conversation, need conversation data in string format
conversation = """
User: Hi, I need help with my order.
"""

# Generate summary
summary = summarizer(conversation, max_length=16, min_length=10, do_sample=False)[0]['summary_text']
print("Summary:", summary)
