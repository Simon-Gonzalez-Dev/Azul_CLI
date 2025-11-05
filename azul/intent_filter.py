"""Intent filter module for detecting false positive file operations."""

from typing import List, Dict


def is_likely_false_positive(
    conversational_part: str, 
    actions: List[Dict], 
    user_prompt: str
) -> bool:
    """
    Analyzes the response to determine if a file operation is likely a hallucination.
    
    Args:
        conversational_part: The conversational text from the AI response
        actions: List of potential file operations extracted
        user_prompt: The original user prompt
        
    Returns:
        True if the actions are likely false positives, False otherwise
    """
    # If no actions, can't be a false positive
    if not actions:
        return False
    
    # Rule 1: The "Just Explaining" Rule
    # If the conversational part contains phrases that indicate the AI is just giving an example,
    # it's likely a false positive.
    explanation_phrases = [
        "here are some of the things i can do",
        "for example",
        "here is the format",
        "i can do things like",
        "here's an example",
        "for instance",
        "this is how",
        "like this",
        "as an example",
        "to illustrate",
        "here's what",
        "this shows",
        "you can see",
    ]
    conversational_lower = conversational_part.lower()
    if any(phrase in conversational_lower for phrase in explanation_phrases):
        return True
    
    # Rule 2: The "Answering a Question" Rule
    # If the user's prompt was a direct question not related to file modification,
    # and the AI generated an action, it's highly suspect.
    question_starters = ["what", "who", "when", "where", "why", "how", "tell me", "explain", "describe"]
    user_prompt_lower = user_prompt.lower().strip()
    
    # Check if prompt starts with question word
    starts_with_question = any(user_prompt_lower.startswith(q) for q in question_starters)
    
    if starts_with_question:
        # Check if prompt also contains action words
        action_words = ["create", "edit", "change", "delete", "update", "save", "apply", "modify", "write", "make"]
        has_action_word = any(word in user_prompt_lower for word in action_words)
        
        # If it's a question but doesn't have action words, likely false positive
        if not has_action_word:
            return True
    
    # Rule 3: The "No Conversational Preamble" Rule
    # A genuine action response, based on our new prompt, should have minimal conversational part.
    # However, if the user prompt contains clear action words, we should be more lenient
    # (allowing explanatory text after a valid action block).
    action_words = ["create", "edit", "change", "delete", "update", "save", "apply", "modify", "write", "make", "remove"]
    user_prompt_lower = user_prompt.lower()
    user_has_action_word = any(word in user_prompt_lower for word in action_words)
    
    # If user has action words and we found actions, be more lenient (allow up to 200 chars)
    # Otherwise, if there's significant conversational text (>50 chars), it's suspicious
    threshold = 200 if user_has_action_word else 50
    
    if actions and len(conversational_part.strip()) > threshold:
        return True
    
    return False

