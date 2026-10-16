"""Finite synthetic curriculum for the 64x64 general appearance experiment."""
SUBJECTS = {
    'car': ('a compact passenger car, side view', ['car', 'cars', 'automobile', 'sedan']),
    'bicycle': ('a bicycle, side view', ['bicycle', 'bicycles', 'bike', 'bikes']),
    'motorcycle': ('a motorcycle, side view', ['motorcycle', 'motorbike']),
    'truck': ('a delivery truck, side view', ['truck', 'trucks']),
    'airplane': ('a passenger airplane, side view', ['airplane', 'aeroplane', 'plane', 'jet']),
    'boat': ('a small sailboat, side view', ['boat', 'sailboat', 'ship']),
    'phone': ('a modern smartphone, three-quarter front view', ['phone', 'phones', 'smartphone', 'mobile phone', 'cellphone']),
    'laptop': ('an open laptop computer, three-quarter front view', ['laptop', 'laptops', 'computer', 'notebook computer']),
    'camera': ('a digital camera, three-quarter front view', ['camera', 'cameras']),
    'headphones': ('a pair of over-ear headphones, front view', ['headphones', 'headphone', 'headset']),
    'watch': ('a wristwatch, front view', ['watch', 'wristwatch', 'watches']),
    'robot': ('a friendly toy robot, front view', ['robot', 'robots']),
    'woman': ('a fictional adult woman, clothed head-and-shoulders portrait, front view', ['woman', 'women', 'lady', 'female', 'person', 'people', 'portrait']),
    'man': ('a fictional adult man, clothed head-and-shoulders portrait, front view', ['man', 'men', 'gentleman', 'male']),
    'dog': ('a sitting pet dog, front view', ['dog', 'dogs', 'puppy']),
    'cat': ('a sitting pet cat, front view', ['cat', 'cats', 'kitten']),
    'horse': ('a standing horse, side view', ['horse', 'horses']),
    'bird': ('a small colorful bird on a branch, side view', ['bird', 'birds', 'parrot']),
    'dragon': ('a fantasy dragon, side view', ['dragon', 'dragons']),
    'flower': ('a single flower in a pot, front view', ['flower', 'flowers', 'rose', 'sunflower']),
    'tree': ('a single leafy tree, full view', ['tree', 'trees']),
    'house': ('a small house, three-quarter exterior view', ['house', 'houses', 'home']),
    'city': ('a city skyline, distant view', ['city', 'skyline', 'cityscape', 'buildings']),
    'mountain': ('a mountain landscape with blue sky', ['mountain', 'mountains', 'landscape']),
    'beach': ('a beach landscape with ocean and blue sky', ['beach', 'ocean', 'sea']),
    'forest': ('a green forest landscape with a path', ['forest', 'woods', 'woodland']),
    'pizza': ('a round pizza on a plate, three-quarter overhead view', ['pizza']),
    'burger': ('a hamburger on a plate, front view', ['burger', 'hamburger']),
    'cup': ('a ceramic coffee cup, three-quarter view', ['cup', 'mug', 'coffee']),
    'chair': ('a single chair, three-quarter front view', ['chair', 'chairs', 'furniture']),
    'shoe': ('a single sneaker shoe, side view', ['shoe', 'shoes', 'sneaker', 'sneakers']),
    'spaceship': ('a fictional spaceship, three-quarter view', ['spaceship', 'spacecraft', 'rocket']),
}


def prompt_for(subject, group):
    description = SUBJECTS[subject][0]
    lighting = ['soft daylight', 'warm studio light', 'cool diffuse light', 'gentle evening light'][group % 4]
    background = 'a simple uncluttered light background' if subject not in ('city', 'mountain', 'beach', 'forest') else 'a clear balanced composition'
    return f'A realistic photograph of {description}, single main subject centered, {background}, {lighting}, complete subject inside frame, sharp detail, no text, no logos'
