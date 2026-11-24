from cael_unified import world_model as W


def ask(text):
    r = W.reply(text)
    return r and r['response'].lower()


def test_people_and_objects_move_together():
    story = ("Anna walked to the garage. She picked up the hammer. Then she headed to the attic. "
             "Anna put down the hammer. Leo rushed to the attic. Where is the hammer?")
    assert ask(story) == 'attic'


def test_giving_and_carrying():
    story = "Omar grabbed the keys. Omar handed the keys to Priya. Priya took the map. What is Priya carrying?"
    assert ask(story) == 'keys,map'
    assert ask("Omar grabbed the keys. Omar handed the keys to Priya. Who gave the keys to Priya?") == 'omar'


def test_time_words_order_events():
    story = ("This afternoon Zoe drove to the office. Yesterday Zoe flew to the airport. "
             "This morning Zoe went to the park. Where was Zoe before the office?")
    assert ask(story) == 'park'


def test_maybe_and_negation():
    assert ask("Kim is either in the lab or the library. Is Kim in the lab?") == 'maybe'
    assert ask("Kim is no longer in the lab. Is Kim in the lab?") == 'no'


def test_deduction_and_route():
    assert ask("Cats are afraid of dogs. Tom is a cat. What is Tom afraid of?") == 'dog'
    assert ask("The hall is north of the kitchen. The study is east of the hall. "
               "How do you go from the kitchen to the study?") == 'north east'


def test_silent_on_ordinary_chat():
    assert W.reply("I went to the store yesterday. Where should I buy cheap milk?") is None
    assert W.reply("My sister moved to Berlin last year. Do you think she likes it?") is None
    assert W.reply("What is the capital of France?") is None
