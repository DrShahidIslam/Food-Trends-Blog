import json

q = json.load(open('topic_queue.json', encoding='utf-8'))
done = [t for t in q if t.get('wp_status') == 'done']
print(f"Total done: {len(done)}")

print("\nLast 25 done topics in topic_queue.json:")
for i, t in enumerate(done[-25:]):
    print(f"{i+1}. '{t.get('topic')}' | Pins: {t.get('pin_count', 0)} | Published: {t.get('published_at')}")
