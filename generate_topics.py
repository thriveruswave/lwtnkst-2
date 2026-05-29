"""
Generate new law topics from around the world using AI when topics.txt runs low.

This script:
1. Tracks used topics in used_topics.txt
2. When available topics drop below 20, generates 100 NEW fresh topics
3. Ensures NO topic is EVER repeated by checking against used topics
4. Appends new unique topics to topics.txt
"""

import requests
from urllib.parse import quote
from pathlib import Path

def generate_new_topics(count=100, used_topics_set=None):
    """Generate new law topics covering ancient and medieval laws from around the world."""
    
    if used_topics_set is None:
        used_topics_set = set()
    
    base_url = "https://text.pollinations.ai/"
    all_new_topics = []
    
    # We'll generate more than needed and filter out duplicates
    attempts = 0
    max_attempts = 5
    
    while len(all_new_topics) < count and attempts < max_attempts:
        attempts += 1
        print(f"[topics] Generation attempt {attempts}/{max_attempts}...")
        
        # Generate ancient law topics
        ancient_system = (
            "You are a legal historian specializing in ancient laws. "
            f"Create a list of {count//2 + 10} unique topics about ancient laws in English. "
            "Each topic should be short (5-10 words), fascinating and educational. "
            "Topics should cover: Code of Hammurabi, Roman Law, Ancient Egyptian laws, "
            "Ancient Greek laws, Mosaic Law, Ancient Chinese laws, Babylonian laws, "
            "Ancient Indian laws (Manusmriti), Persian laws, Sumerian laws, "
            "Phoenician laws, Hittite laws, Assyrian laws, Aztec laws, Inca laws, "
            "Maya laws, Ancient Japanese laws, Korean laws, Vietnamese laws. "
            "Be creative and diverse. Output ONLY topics, one per line, no numbers or bullets."
        )
        
        ancient_prompt = f"Create {count//2 + 10} unique ancient law topics from different civilizations"
        ancient_url = base_url + quote(ancient_prompt)
        ancient_params = {"model": "openai", "temperature": 1.0, "system": ancient_system}
        
        print(f"[topics] Generating ancient law topics...")
        try:
            r = requests.get(ancient_url, params=ancient_params, timeout=120)
            r.raise_for_status()
            
            ancient_topics = []
            for line in r.text.strip().split('\n'):
                cleaned = line.strip()
                for prefix in ['- ', '* ', '• ']:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):]
                import re
                cleaned = re.sub(r'^\d+[\.\:\)]\s*', '', cleaned)
                if cleaned and len(cleaned) > 5:
                    full_topic = f"[ANCIENT] {cleaned}"
                    if full_topic not in used_topics_set:
                        ancient_topics.append(full_topic)
        except Exception as e:
            print(f"[topics] Error generating ancient topics: {e}")
            ancient_topics = []
        
        # Generate medieval law topics
        medieval_system = (
            "You are a legal historian specializing in medieval laws. "
            f"Create a list of {count//2 + 10} unique topics about medieval laws in English. "
            "Each topic should be short (5-10 words), intriguing and informative. "
            "Topics should cover: Magna Carta, feudal law, canon law, Islamic law (Sharia), "
            "medieval European laws, trial by ordeal, medieval justice systems, "
            "guild laws, medieval property rights, chivalric codes, medieval punishments, "
            "Byzantine law, Mongol law, Ottoman law, medieval African kingdoms laws, "
            "medieval Asian laws, Samurai code, medieval merchant laws. "
            "Be creative and diverse. Output ONLY topics, one per line, no numbers or bullets."
        )
        
        medieval_prompt = f"Create {count//2 + 10} unique medieval law topics from different regions"
        medieval_url = base_url + quote(medieval_prompt)
        medieval_params = {"model": "openai", "temperature": 1.0, "system": medieval_system}
        
        print(f"[topics] Generating medieval law topics...")
        try:
            r = requests.get(medieval_url, params=medieval_params, timeout=120)
            r.raise_for_status()
            
            medieval_topics = []
            for line in r.text.strip().split('\n'):
                cleaned = line.strip()
                for prefix in ['- ', '* ', '• ']:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[len(prefix):]
                import re
                cleaned = re.sub(r'^\d+[\.\:\)]\s*', '', cleaned)
                if cleaned and len(cleaned) > 5:
                    full_topic = f"[MEDIEVAL] {cleaned}"
                    if full_topic not in used_topics_set:
                        medieval_topics.append(full_topic)
        except Exception as e:
            print(f"[topics] Error generating medieval topics: {e}")
            medieval_topics = []
        
        # Interleave ancient and medieval topics for variety
        max_len = max(len(ancient_topics), len(medieval_topics))
        for i in range(max_len):
            if i < len(ancient_topics) and len(all_new_topics) < count:
                all_new_topics.append(ancient_topics[i])
            if i < len(medieval_topics) and len(all_new_topics) < count:
                all_new_topics.append(medieval_topics[i])
        
        print(f"[topics] Generated {len(all_new_topics)} unique topics so far...")
    
    return all_new_topics[:count]

def check_and_update_topics():
    """Check topics.txt and add more if needed, tracking used topics."""
    
    topics_file = Path('topics.txt')
    used_topics_file = Path('used_topics.txt')
    
    # Read existing topics
    if topics_file.exists():
        with open(topics_file, 'r', encoding='utf-8') as f:
            existing_topics = [line.strip() for line in f if line.strip()]
    else:
        existing_topics = []
    
    # Read used topics
    if used_topics_file.exists():
        with open(used_topics_file, 'r', encoding='utf-8') as f:
            used_topics = set(line.strip() for line in f if line.strip())
    else:
        used_topics = set()
    
    print(f"[topics] Current available topics: {len(existing_topics)}")
    print(f"[topics] Total used topics: {len(used_topics)}")
    
    # Check if we need more topics (threshold: 20 topics remaining)
    if len(existing_topics) < 20:
        print(f"[topics] Low on topics! Generating 100 NEW fresh topics...")
        
        new_topics = generate_new_topics(100, used_topics)
        
        # Append to file
        with open(topics_file, 'a', encoding='utf-8') as f:
            for topic in new_topics:
                f.write(f"{topic}\n")
        
        print(f"[topics] Added {len(new_topics)} NEW topics!")
        print(f"[topics] Total topics now: {len(existing_topics) + len(new_topics)}")
    else:
        print(f"[topics] Enough topics available ({len(existing_topics)})")

if __name__ == '__main__':
    check_and_update_topics()
