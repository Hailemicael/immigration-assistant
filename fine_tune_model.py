# from datasets import load_dataset
# from transformers import (
#     AutoModelForCausalLM,
#     AutoTokenizer,
#     TrainingArguments,
#     Trainer,
#     DataCollatorForLanguageModeling
# )
# import os
# import json
# import torch

# def prepare_dataset(dataset_path):
#     """Prepare the dataset for training"""
    
#     # Load dataset
#     with open(dataset_path, "r") as f:
# #         data = json.load(f)
    
# #     # Create dataset in the format expected by transformers
# #     formatted_data = []
    
# #     for i in range(0, len(data["messages"]), 2):
# #         if i+1 < len(data["messages"]):
# #             question = data["messages"][i]["content"]
# #             answer = data["messages"][i+1]["content"]
            
# #             formatted_data.append({
# #                 "text": f"### Question: {question}\n\n### Answer: {answer}"
# #             })
    
# #     # Save formatted data to a temporary file
# #     temp_file = "/home/hailemicaelyimer/Desktop/immigration-assistant/data/training/formatted_dataset.json"
# #     with open(temp_file, "w") as f:
# #         json.dump({"data": formatted_data}, f)
    
# #     # Load dataset from temp file
# #     dataset = load_dataset("json", data_files=temp_file, field="data")
# #     return dataset

# # def fine_tune_model(dataset_path, output_dir="/home/hailemicaelyimer/Desktop/immigration-assistant/data/models/fine-tuned-immigration"):
# #     """Fine-tune a model on the immigration dataset"""
    
# #     # Prepare dataset
# #     dataset = prepare_dataset(dataset_path)
    
# #     # Initialize tokenizer and model
# #     model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"  # A smaller model for faster fine-tuning
    
# #     tokenizer = AutoTokenizer.from_pretrained(model_name)
# #     model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
    
# #     # Make sure the tokenizer has a pad token
# #     if tokenizer.pad_token is None:
# #         tokenizer.pad_token = tokenizer.eos_token
    
# #     # Tokenize the dataset
# #     def tokenize_function(examples):
# #         return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=512)
    
# #     tokenized_dataset = dataset.map(tokenize_function, batched=True)
    
# #     # Configure training
# #     training_args = TrainingArguments(
# #         output_dir=output_dir,
# #         overwrite_output_dir=True,
# #         num_train_epochs=3,
# #         per_device_train_batch_size=4,
# #         save_steps=100,
# #         save_total_limit=2,
# #         logging_steps=10,
# #         learning_rate=2e-5,
# #         weight_decay=0.01,
# #         fp16=True,
# #         remove_unused_columns=False,
# #     )
    
# #     # Create Trainer
# #     trainer = Trainer(
# #         model=model,
# #         args=training_args,
# #         train_dataset=tokenized_dataset["train"],
# #         tokenizer=tokenizer,
# #         data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
# #     )
    
# #     # Train the model
# #     trainer.train()
    
# #     # Save the model
# #     trainer.save_model(output_dir)
# #     tokenizer.save_pretrained(output_dir)
    
# #     print(f"Model fine-tuned and saved to {output_dir}")
# #     return output_dir

# # if __name__ == "__main__":
# #     # Create dataset if it doesn't exist
# #     if not os.path.exists("/home/hailemicaelyimer/Desktop/immigration-assistant/data/training/immigration_qa_dataset.json"):
# #         from create_dataset import create_training_dataset
# #         dataset_path = create_training_dataset()
# #     else:
# #         dataset_path = "/home/hailemicaelyimer/Desktop/immigration-assistant/data/training/immigration_qa_dataset.json"
    
# #     # Fine-tune the model
# #     model_path = fine_tune_model(dataset_path)
# #     print(f"Fine-tuning complete. Model saved to {model_path}")

# from datasets import load_dataset
# from transformers import (
#     AutoModelForCausalLM,
#     AutoTokenizer,
#     TrainingArguments,
#     Trainer,
#     DataCollatorForLanguageModeling
# )
# import os
# import json
# import torch

# def prepare_dataset(dataset_path):
#     """Prepare the dataset for training"""
    
#     # Load dataset
#     with open(dataset_path, "r") as f:
#         data = json.load(f)
    
#     # Create dataset in the format expected by transformers
#     formatted_data = []
    
#     for i in range(0, len(data["messages"]), 2):
#         if i+1 < len(data["messages"]):
#             question = data["messages"][i]["content"]
#             answer = data["messages"][i+1]["content"]
            
#             formatted_data.append({
#                 "text": f"### Question: {question}\n\n### Answer: {answer}"
#             })
    
#     # Save formatted data to a temporary file
#     temp_file = "data/training/formatted_dataset.json"
#     with open(temp_file, "w") as f:
#         json.dump({"data": formatted_data}, f)
    
#     # Load dataset from temp file
#     dataset = load_dataset("json", data_files=temp_file, field="data")
#     return dataset

# def fine_tune_model(dataset_path, output_dir="models/fine-tuned-immigration"):
#     """Fine-tune a model on the immigration dataset"""
    
#     # Prepare dataset
#     dataset = prepare_dataset(dataset_path)
    
#     # Initialize tokenizer and model
#     model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"  # A smaller model for faster fine-tuning
    
#     tokenizer = AutoTokenizer.from_pretrained(model_name)
#     model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)
    
#     # Make sure the tokenizer has pad and eos tokens set
#     if tokenizer.pad_token is None:
#         tokenizer.pad_token = tokenizer.eos_token
    
#     # Define tokenization function with proper padding and truncation
#     def tokenize_function(examples):
#         # Apply padding and truncation explicitly
#         return tokenizer(
#             examples["text"], 
#             padding="max_length", 
#             truncation=True, 
#             max_length=512,
#             return_tensors=None  # This is important - don't return tensors here
#         )
    
#     # Process the dataset
#     tokenized_dataset = dataset.map(
#         tokenize_function, 
#         batched=True,
#         remove_columns=["text"]  # Remove original text column
#     )
    
#     # Verify the dataset structure
#     print(f"Dataset features: {tokenized_dataset['train'].features}")
#     print(f"First example: {tokenized_dataset['train'][0]}")
    
#     # Configure training
#     training_args = TrainingArguments(
#         output_dir=output_dir,
#         overwrite_output_dir=True,
#         num_train_epochs=3,
#         per_device_train_batch_size=4,
#         save_steps=100,
#         save_total_limit=2,
#         logging_steps=10,
#         learning_rate=2e-5,
#         weight_decay=0.01,
#         fp16=True,
#     )
    
#     # Use proper data collator for language modeling
#     data_collator = DataCollatorForLanguageModeling(
#         tokenizer=tokenizer,
#         mlm=False
#     )
    
#     # Create Trainer
#     trainer = Trainer(
#         model=model,
#         args=training_args,
#         train_dataset=tokenized_dataset["train"],
#         data_collator=data_collator,
#     )
    
#     # Train the model
#     trainer.train()
    
#     # Save the model
#     trainer.save_model(output_dir)
#     tokenizer.save_pretrained(output_dir)
    
#     print(f"Model fine-tuned and saved to {output_dir}")
#     return output_dir

# if __name__ == "__main__":
#     # Create dataset if it doesn't exist
#     if not os.path.exists("data/training/immigration_qa_dataset.json"):
#         from create_dataset import create_training_dataset
#         dataset_path = create_training_dataset()
#     else:
#         dataset_path = "data/training/immigration_qa_dataset.json"
    
#     # Fine-tune the model
#     model_path = fine_tune_model(dataset_path)
#     print(f"Fine-tuning complete. Model saved to {model_path}")

from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
import os
import json
import torch
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def prepare_dataset(dataset_path):
    """Prepare the dataset for training"""
    
    # Load dataset
    with open(dataset_path, "r") as f:
        data = json.load(f)
    
    # Create dataset in the format expected by transformers
    formatted_data = []
    
    for i in range(0, len(data["messages"]), 2):
        if i+1 < len(data["messages"]):
            question = data["messages"][i]["content"]
            answer = data["messages"][i+1]["content"]
            
            formatted_data.append({
                "text": f"### Question: {question}\n\n### Answer: {answer}"
            })
    
    # Save formatted data to a temporary file
    temp_file = "data/training/formatted_dataset.json"
    with open(temp_file, "w") as f:
        json.dump({"data": formatted_data}, f)
    
    # Load dataset from temp file
    dataset = load_dataset("json", data_files=temp_file, field="data")
    return dataset

def fine_tune_model(dataset_path, output_dir="models/fine-tuned-immigration"):
    """Fine-tune a model on the immigration dataset"""
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Prepare dataset
    dataset = prepare_dataset(dataset_path)
    
    # Choose a smaller model that will fit in GPU memory
    model_name = "distilgpt2"  # Much smaller than TinyLlama
    
    logger.info(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    
    # Make sure the tokenizer has pad and eos tokens set
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Define tokenization function with proper padding and truncation
    def tokenize_function(examples):
        outputs = tokenizer(
            examples["text"], 
            padding="max_length", 
            truncation=True, 
            max_length=256,  # Reduce sequence length to save memory
            return_tensors=None  # Important - don't return tensors here
        )
        # Add labels for causal language modeling
        outputs["labels"] = outputs["input_ids"].copy()
        return outputs
    
    # Process the dataset
    tokenized_dataset = dataset.map(
        tokenize_function, 
        batched=True,
        remove_columns=["text"]  # Remove original text column
    )
    
    # Display sample for debugging
    logger.info(f"Dataset features: {tokenized_dataset['train'].features}")
    logger.info(f"First example: {tokenized_dataset['train'][0]}")
    
    # Load model after tokenization to save memory
    logger.info("Loading model")
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
    # Configure training with minimal settings to avoid memory issues
    training_args = TrainingArguments(
        output_dir=output_dir,
        overwrite_output_dir=True,
        num_train_epochs=3,
        per_device_train_batch_size=1,  # Reduce batch size
        gradient_accumulation_steps=4,  # Accumulate gradients to compensate for small batch size
        save_steps=50,
        save_total_limit=2,
        logging_steps=10,
        learning_rate=1e-5,  # Lower learning rate
        weight_decay=0.01,
        fp16=False,  # Turn off mixed precision to avoid potential issues
        dataloader_pin_memory=False,  # Disable pinned memory
        no_cuda=False,  # Set to True if you want to force CPU training
    )
    
    # Use proper data collator for language modeling
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    # Create Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset["train"],
        data_collator=data_collator,
    )
    
    # Train the model
    logger.info("Starting training")
    trainer.train()
    
    # Save the model
    logger.info("Saving model")
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    logger.info(f"Model fine-tuned and saved to {output_dir}")
    return output_dir

if __name__ == "__main__":
    # Create dataset if it doesn't exist
    if not os.path.exists("data/training/immigration_qa_dataset.json"):
        from create_dataset import create_training_dataset
        dataset_path = create_training_dataset()
    else:
        dataset_path = "data/training/immigration_qa_dataset.json"
    
    # Fine-tune the model
    try:
        model_path = fine_tune_model(dataset_path)
        print(f"Fine-tuning complete. Model saved to {model_path}")
    except Exception as e:
        logger.error(f"Error during fine-tuning: {e}")
        
        # Try to force CPU training if GPU is causing issues
        print("Attempting to train on CPU instead...")
        os.environ["CUDA_VISIBLE_DEVICES"] = ""  # Disable CUDA
        try:
            model_path = fine_tune_model(dataset_path)
            print(f"Fine-tuning complete on CPU. Model saved to {model_path}")
        except Exception as e:
            logger.error(f"Error during CPU fine-tuning: {e}")