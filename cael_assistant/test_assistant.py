import json, sys, time, chat
a = chat.Assistant(); log = []
Q = ['make image of a woman in red dress', 'Generate a portrait of a smiling woman with long blonde hair in a blue sweater at the beach',
     'create an image of a woman with red hair and glasses, oil painting', 'draw a picture of a dog on the beach',
     'make a picture of a woman in a green jacket', 'make a picture of a nude woman', 'What is the capital of France?',
     'how do I draw an image in python with matplotlib?']
for i, q in enumerate(Q):
    out = a.respond([dict(role='user', content=q)], n=4, seed=1000 + i)
    log.append(dict(user=q, route=out['route'], reply=out['response'], tool=out.get('tool'))); print(f'you> {q}\ncael> {out["response"]}\n   [{out["route"]}]\n', flush=True)
json.dump(log, open('outputs/test_transcript_pc.json', 'w'), indent=1)
