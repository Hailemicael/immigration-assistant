import json
import os

def create_training_dataset():
    """Create a synthetic dataset for fine-tuning an immigration assistant model"""
    
    # Create directory for datasets
    os.makedirs("/home/hailemicaelyimer/Desktop/immigration-assistant/data/training", exist_ok=True)
    
    # Create a list of immigration Q&A pairs
    qa_pairs = [
        {
            "question": "How do I apply for a green card based on marriage?",
            "answer": "To apply for a green card through marriage to a U.S. citizen, you need to file Form I-130 (Petition for Alien Relative) and Form I-485 (Application to Register Permanent Residence). Your spouse must file the I-130 petition on your behalf. You'll need to provide evidence of a bona fide marriage, attend a biometrics appointment, and participate in an interview. The process typically takes 1-2 years depending on your location."
        },
        {
            "question": "What are the requirements for U.S. citizenship?",
            "answer": "To become a U.S. citizen through naturalization, you must: (1) Be a permanent resident for at least 5 years (or 3 years if married to a U.S. citizen), (2) Be at least 18 years old, (3) Demonstrate continuous residence, (4) Demonstrate good moral character, (5) Pass an English test (reading, writing, speaking), (6) Pass a civics test about U.S. history and government, and (7) Take an oath of allegiance to the U.S. You apply using Form N-400."
        },
        {
            "question": "How much does it cost to apply for a green card?",
            "answer": "The cost of applying for a green card varies based on your situation. As of 2025, filing Form I-485 (Adjustment of Status) costs $1,440 for most applicants, which includes the $85 biometrics fee. If you're applying through a family member, they'll also need to file Form I-130, which costs $535. Additional costs may include the medical examination (typically $200-$400), and potentially Form I-765 for work authorization and Form I-131 for travel permission, though these are currently included with the I-485 fee."
        },
        {
            "question": "What is the USCIS processing time for citizenship applications?",
            "answer": "USCIS processing times for citizenship applications (Form N-400) typically range from 8 to 12 months, but can vary significantly based on your location, case complexity, and USCIS workload. Some field offices process applications in as little as 6 months, while others may take over 2 years. You can check current processing times for your specific field office on the USCIS website."
        },
        {
            "question": "What documents do I need for a family-based green card application?",
            "answer": "For a family-based green card application, you typically need: (1) Form I-130 and I-485, (2) Proof of family relationship (marriage certificate, birth certificate), (3) Proof of petitioner's U.S. citizenship or permanent residence, (4) Financial documents including Form I-864 Affidavit of Support, (5) Medical examination results on Form I-693, (6) Applicant's birth certificate, passport, and photos, (7) Immigration history documents, and (8) If applicable, certified translations of non-English documents."
        },
        {
            "question": "How do I check my immigration case status?",
            "answer": "You can check your immigration case status online through the USCIS Case Status Online tool at uscis.gov. You'll need your receipt number, which starts with three letters (such as IOE, MSC, EAC, SRC, LIN, WAC) followed by 10 numbers. Alternatively, you can call the USCIS Contact Center at 1-800-375-5283 or schedule an InfoPass appointment at a local USCIS field office for more complex inquiries."
        },
        {
            "question": "What is the difference between an immigrant visa and a green card?",
            "answer": "An immigrant visa and a green card serve similar purposes but come at different stages of the immigration process. An immigrant visa is issued by a U.S. consulate or embassy abroad and allows you to enter the U.S. as a permanent resident. A green card (Form I-551) is the physical proof of your permanent resident status and is issued after you enter the U.S. with an immigrant visa or after your adjustment of status application is approved within the U.S. Both grant you permanent resident status."
        },
        {
            "question": "How do I renew my green card?",
            "answer": "To renew your green card, file Form I-90 (Application to Replace Permanent Resident Card) either online or by mail. You should apply to renew your green card if it's expired or will expire within the next 6 months. Include a copy of your current green card, supporting documents, and the filing fee ($540 total as of 2025, including $85 biometrics fee). After filing, you'll receive a receipt notice, attend a biometrics appointment, and receive your new card by mail, typically within 5-12 months."
        },
        {
            "question": "What happens if my green card application is denied?",
            "answer": "If your green card application is denied, USCIS will send you a denial notice explaining the reasons. You generally have three options: (1) File a motion to reopen or reconsider with the same office that made the decision if you have new evidence or believe there was a legal or procedural error, (2) Appeal to the Administrative Appeals Office (AAO) or Board of Immigration Appeals (BIA) using Form I-290B within 30 days, or (3) Reapply with a new application addressing the issues that led to the denial."
        },
        {
            "question": "How do I qualify for asylum in the United States?",
            "answer": "To qualify for asylum in the U.S., you must demonstrate that you've been persecuted or have a well-founded fear of persecution in your home country due to your race, religion, nationality, membership in a particular social group, or political opinion. You must apply within one year of arriving in the U.S. using Form I-589, unless you qualify for an exception. The process includes an interview with an asylum officer or a hearing with an immigration judge, and you'll need to provide detailed documentation supporting your claim."
        }
    ]
    
    # Format data for fine-tuning
    formatted_data = {
        "model_format": "instruction",
        "messages": []
    }
    
    for pair in qa_pairs:
        formatted_data["messages"].append({
            "role": "user",
            "content": pair["question"]
        })
        formatted_data["messages"].append({
            "role": "assistant",
            "content": pair["answer"]
        })
    
    # Save dataset to file
    with open("data/training/immigration_qa_dataset.json", "w") as f:
        json.dump(formatted_data, f, indent=2)
    
    print(f"Created training dataset with {len(qa_pairs)} Q&A pairs")
    return "data/training/immigration_qa_dataset.json"

if __name__ == "__main__":
    create_training_dataset()