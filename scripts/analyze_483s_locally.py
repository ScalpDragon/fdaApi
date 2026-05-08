# SUMMARY:
# This script prompts the user for a CSV file name containing FDA 483 citations.
# It uses the pandas library to generate a statistical summary of the data 
# (top CFR violations and program areas). Finally, it sends this summary to a 
# local Ollama LLM (gemma4:e2b) to generate compliance and trending insights.

import pandas as pd
import ollama
import os

def main():
    # Prompt the user to input the CSV file name from the terminal
    csv_file = input("Enter the CSV file name (e.g., drugs_483_citations_2025.csv): ")
    print(f"Loading data from {csv_file}...")
    try:
        df = pd.read_csv(csv_file)
    except FileNotFoundError:
        print(f"Error: Could not find {csv_file}")
        return

    # Generate a summary using pandas
    print("Summarizing data...")
    total_citations = len(df)
    
    # Get top 5 most frequent CFR numbers
    top_cfr = df['ActCFRNumber'].value_counts().head(5)
    
    # Get top 5 program areas
    top_areas = df['ProgramArea'].value_counts().head(5)

    # Convert the pandas series to strings for the prompt
    summary_text = f"""
    FDA 483 Citations Summary for 2025:
    Total Citations: {total_citations}
    
    Top 5 Act/CFR Numbers Violated:
    {top_cfr.to_string()}
    
    Top 5 Program Areas:
    {top_areas.to_string()}
    """

    print("\n--- Data Summary Generated ---")
    print(summary_text)
    print("------------------------------\n")

    print("Sending summary to local model (gemma4:e2b) for insights...")
    
    # Craft the prompt for the LLM
    prompt = f"""
    You are an expert in FDA compliance and manufacturing quality control.
    I have extracted some data regarding FDA 483 citations for the year 2025.
    
    Here is the summary of the data:
    {summary_text}
    
    Based on this summary, please provide a short, insightful analysis. 
    What do these top violations suggest about the current state of industry compliance?
    What areas should manufacturers prioritize based on these trends?
    """

    # Interact with the local model
    try:
        response = ollama.chat(model='gemma4:e2b', messages=[
            {
                'role': 'user',
                'content': prompt
            }
        ])
        
        print("\n=== AI Analysis ===")
        print(response['message']['content'])
        print("===================\n")
        
    except Exception as e:
        print(f"An error occurred while communicating with Ollama: {e}")
        print("Make sure Ollama is running and the 'gemma4:e2b' model is downloaded.")

if __name__ == "__main__":
    main()
