OLD_CAR = "с"
OLD_CAR_LABEL = "Старый завоз"
CURRENT_LABEL = "Текущий"
SEED_CARS = ["к10", "к20", "к25", "мерс210", "пб5+", OLD_CAR]
MAX_PRICE = 2_147_483_647


def car_label(name: str) -> str:
    return OLD_CAR_LABEL if name == OLD_CAR else name
