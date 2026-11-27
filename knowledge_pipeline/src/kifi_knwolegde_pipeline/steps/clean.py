import re
from typing import Annotated
from loguru import logger
from zenml import step, get_step_context
from llm_twin.domain.documents import MessagesDocument


def _fix_mojibake(text: str) -> str:
    if not text:
        return text
    try:
        return text.encode("cp1252").decode("utf-8")
    except Exception:
        pass
    try:
        return text.encode("latin-1").decode("utf-8")
    except Exception:
        pass
    return text


def _should_drop_content(content: str) -> bool:
    if content is None:
        return True
    if not isinstance(content, str):
        return True
    
    # Pre-clean strings (remove double quotes, "(edited)" and outer whitespace)
    content_clean = content.replace('"', '').replace('(edited)', '').strip()
    
    # Check for empty / single-character messages
    if len(content_clean) <= 1:
        return True
        
    content_upper = content_clean.upper()
    if content_upper in ("NAN", "NONE", "NULL"):
        return True
        
    # Exact matches for blacklist (including variants for Mojibake since they are raw files)
    if content_clean in [
        "Vous avez envoyÃ© une piÃ¨ce jointe.",
        "Vous avez envoyé une pièce jointe.",
        "Audio call ended",
        "00799999004417259635",
        "nonoletop2.2",
        "You missed a video chat",
        "Liked a message",
    ]:
        return True
        
    # Wildcard / prefix / suffix matches
    
    # Reacted * to your message
    if re.match(r"^Reacted\s+.*\s+to your message\s*$", content_clean) or (
        content_clean.startswith("Reacted ") and "to your message" in content_clean
    ):
        return True
        
    # https:* or any link
    if "https:" in content_clean or "http:" in content_clean or "www." in content_clean:
        return True
        
    # * a envoyÃ© une piÃ¨ce jointe. / piece jointe
    if (
        content_clean.endswith("a envoyÃ© une piÃ¨ce jointe.")
        or content_clean.endswith("a envoyé une pièce jointe.")
    ):
        return True
        
    # * started an audio call
    if content_clean.endswith("started an audio call"):
        return True
        
    # *@gmail.com
    if "@gmail.com" in content_clean:
        return True
        
    return False


def _clean_text_content(content: str) -> str:
    # 1. Remove double quotes
    content = content.replace('"', '')
    # 2. Remove only the "(edited)" word
    content = content.replace('(edited)', '')
    # 3. Strip leading/trailing whitespaces
    content = content.strip()
    # 4. Make repeated characters that are more then 3 only 2 (e.g. hhhhh -> hh)
    content = re.sub(r"(?s)(.)\1{3,}", r"\1\1", content)
    return content


def _merge_group(msg_group: list[dict], participant_name: str) -> dict:
    if len(msg_group) == 1:
        return msg_group[0]
        
    # Join contents by newline
    contents = [m.get("content", "") for m in msg_group]
    merged_content = "\n".join(c for c in contents if c)
    
    # Calculate mean timestamp
    timestamps = [m.get("timestamp_ms", 0) for m in msg_group]
    mean_timestamp = int(round(sum(timestamps) / len(timestamps)))
    
    # Re-apply clean text content to clean any repeated chars that might appear after merge
    final_content = _clean_text_content(merged_content)
    
    return {
        "sender_name": msg_group[0].get("sender_name"),
        "timestamp_ms": mean_timestamp,
        "content": final_content,
        "participant_name": participant_name,
    }


@step
def clean_messages(
    raw_messages: list[MessagesDocument],
) -> Annotated[list[MessagesDocument], "cleaned_messages"]:
    cleaned_docs = []
    
    for doc in raw_messages:
        # Step 1: Remove discussions with more than 1 participant
        # Filter: unique sender_name values inside messages
        unique_senders = {msg.get("sender_name") for msg in doc.messages if msg.get("sender_name") is not None}
        if len(unique_senders) > 2:
            logger.info(f"Skipping MessagesDocument {doc.id}: more than 1 participant (has {len(unique_senders)} unique senders)")
            continue
            
        # Step 2: Remove message logs where the number of messages is less than 100
        if len(doc.messages) < 100:
            logger.info(f"Skipping MessagesDocument {doc.id}: too few messages ({len(doc.messages)} < 100)")
            continue
            
        step3_messages = []
        for msg in doc.messages:
            content = msg.get("content")
            
            # Step 3: Regex cleaning (blacklist, double quotes, (edited), single char checks)
            if _should_drop_content(content):
                continue
                
            cleaned_content = _clean_text_content(content)
            
            # Re-check length of content after cleaning
            if len(cleaned_content) <= 1:
                continue
                
            # Drop any feature except sender_name, timestamp_ms, content, participant_name
            cleaned_msg = {
                "sender_name": msg.get("sender_name"),
                "timestamp_ms": msg.get("timestamp_ms"),
                "content": cleaned_content,
                "participant_name": doc.participant_name,
            }
            step3_messages.append(cleaned_msg)
            
        if not step3_messages:
            continue
            
        # Step 3: Sort by timestamp ascending to correctly merge consecutive messages
        step3_messages.sort(key=lambda m: m.get("timestamp_ms", 0))
        
        # Merge consecutive messages from same sender within 2 minutes
        merged_messages = []
        current_group = []
        
        for msg in step3_messages:
            if not current_group:
                current_group.append(msg)
            else:
                prev_msg = current_group[-1]
                same_sender = msg.get("sender_name") == prev_msg.get("sender_name")
                time_diff = msg.get("timestamp_ms", 0) - prev_msg.get("timestamp_ms", 0)
                within_two_min = time_diff <= 120000
                
                if same_sender and within_two_min:
                    current_group.append(msg)
                else:
                    merged_messages.append(_merge_group(current_group, doc.participant_name))
                    current_group = [msg]
                    
        if current_group:
            merged_messages.append(_merge_group(current_group, doc.participant_name))
            
        # Step 5: Fix Mojibake by encoding from latin1/cp1252 and decoding to utf-8 (Final Step)
        # Apply to participant_name, sender_name, content
        fixed_participant_name = _fix_mojibake(doc.participant_name)
        doc.participant_name = fixed_participant_name
        
        for msg in merged_messages:
            if "sender_name" in msg and msg["sender_name"]:
                msg["sender_name"] = _fix_mojibake(msg["sender_name"])
            if "participant_name" in msg and msg["participant_name"]:
                msg["participant_name"] = fixed_participant_name
            if "content" in msg and msg["content"]:
                msg["content"] = _fix_mojibake(msg["content"])
                
        doc.messages = merged_messages
        
        # Reset ID to None and recompute composite ID hash for the cleaned messages
        doc.id = None
        doc.set_composite_id()
        
        cleaned_docs.append(doc)
        
    try:
        step_context = get_step_context()
        metadata = {
            "num_raw_documents": len(raw_messages),
            "num_cleaned_documents": len(cleaned_docs),
        }
        step_context.add_output_metadata(output_name="cleaned_messages", metadata=metadata)
    except Exception as e:
        logger.warning(f"Failed to add step metadata: {e}")
        
    return cleaned_docs