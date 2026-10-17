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


ADDITIONAL_SUBJECTS = {
    'bus': ('a city bus, side view', ['bus', 'buses']),
    'train': ('a railway locomotive, side view', ['train', 'locomotive']),
    'helicopter': ('a helicopter, side view', ['helicopter', 'helicopters']),
    'tractor': ('a farm tractor, side view', ['tractor', 'tractors']),
    'tablet': ('a tablet computer, three-quarter front view', ['tablet', 'tablets']),
    'monitor': ('a desktop computer monitor on its stand, front view', ['monitor', 'computer monitor']),
    'keyboard': ('a computer keyboard, three-quarter overhead view', ['keyboard', 'computer keyboard']),
    'computer_mouse': ('a computer mouse, three-quarter overhead view', ['computer mouse', 'pc mouse']),
    'television': ('a flat screen television on its stand, front view', ['television', 'tv']),
    'sofa': ('a two-seat sofa, three-quarter front view', ['sofa', 'couch']),
    'table': ('a wooden dining table, three-quarter front view', ['table', 'dining table']),
    'bed': ('a bed with pillows and a blanket, three-quarter front view', ['bed', 'beds']),
    'lamp': ('a table lamp with a fabric shade, front view', ['lamp', 'table lamp']),
    'bottle': ('a glass water bottle, front view', ['bottle', 'bottles']),
    'book': ('a closed hardcover book, three-quarter view', ['book', 'books']),
    'apple': ('a single red apple with a stem, front view', ['apple', 'apples']),
    'banana': ('a single yellow banana, side view', ['banana', 'bananas']),
    'cake': ('a small round decorated cake on a plate, front view', ['cake', 'cakes']),
    'guitar': ('an acoustic guitar, front view', ['guitar', 'guitars']),
    'elephant': ('a standing elephant, side view', ['elephant', 'elephants']),
    'lion': ('a standing male lion with a mane, side view', ['lion', 'lions']),
    'fish': ('a single tropical fish, side view', ['fish', 'tropical fish']),
    'castle': ('a medieval stone castle, three-quarter exterior view', ['castle', 'castles']),
    'waterfall': ('a waterfall surrounded by rocks and green trees', ['waterfall', 'waterfalls']),
}


def curriculum(name='base'):
    if name == 'base':
        return SUBJECTS
    if name == 'expanded':
        return {**SUBJECTS, **ADDITIONAL_SUBJECTS}
    if name == 'portraits':
        return {key: SUBJECTS[key] for key in ('woman', 'man')}
    raise ValueError('Unknown synthetic image curriculum')


def prompt_for(subject, group, curriculum_name='base'):
    if curriculum_name == 'portraits':
        if subject not in ('woman', 'man'):
            raise ValueError('Portrait curriculum contains only adult woman/man subjects')
        age = [25, 35, 45, 55][group % 4]
        hair = ['dark hair', 'brown hair', 'fair hair', 'grey hair'][(group // 4) % 4]
        return (f'A sharply focused studio headshot photograph of one fictional adult {subject}, age {age}, {hair}, '
                'straight-on front view, neutral expression, both eyes open looking directly at the camera, '
                'natural symmetrical facial proportions, detailed eyes, natural skin texture, '
                'whole head and clothed shoulders visible, face centered and occupying most of the frame, '
                'plain light grey background, soft diffuse frontal lighting, no text, no logos')
    description = curriculum(curriculum_name)[subject][0]
    lighting = ['soft daylight', 'warm studio light', 'cool diffuse light', 'gentle evening light'][group % 4]
    background = 'a simple uncluttered light background' if subject not in ('city', 'mountain', 'beach', 'forest', 'waterfall') else 'a clear balanced composition'
    return f'A realistic photograph of {description}, single main subject centered, {background}, {lighting}, complete subject inside frame, sharp detail, no text, no logos'
