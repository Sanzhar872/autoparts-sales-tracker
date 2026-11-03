import pytest

from app.constants import SEED_CARS
from app.parser import ParseError, normalize_car, parse_line, part_key

CARS = set(SEED_CARS)


def parse(text):
    return parse_line(text, CARS)


@pytest.mark.parametrize(
    ("text", "is_return", "car", "code", "part", "price"),
    [
        ("мерс210 сафа левый правый - 25000", False, "мерс210", None, "сафа левый правый", 25000),
        ("к20 капот с обшивкой - 70 000", False, "к20", None, "капот с обшивкой", 70000),
        ("С ТКЕ щиток прибора - 35000", False, "с", "ТКЕ", "щиток прибора", 35000),
        ("возврат к20 капот с обшивкой - 70000", True, "к20", None, "капот с обшивкой", 70000),
        ("возврат С ТКЕ щиток прибора - 35000", True, "с", "ТКЕ", "щиток прибора", 35000),
    ],
)
def test_examples(text, is_return, car, code, part, price):
    parsed = parse(text)
    assert (parsed.is_return, parsed.car, parsed.old_car_code, parsed.part, parsed.price) == (
        is_return, car, code, part, price,
    )


def test_price_with_spaces_and_extra_whitespace():
    parsed = parse("   к20   капот    с обшивкой  -  1 250 000  ")
    assert parsed.part == "капот с обшивкой"
    assert parsed.price == 1_250_000


def test_latin_car_names():
    assert parse("K20 капот - 1000").car == "к20"
    old = parse("C abc щиток - 1000")  # латинская C
    assert old.car == "с"
    assert old.old_car_code == "ABC"
    assert parse("пБ5+ дверь - 100").car == "пб5+"
    assert normalize_car("MEPC210") == "мерс210"


@pytest.mark.parametrize("dash", ["-", "–", "—"])
def test_all_dashes(dash):
    parsed = parse(f"к20 капот {dash} 5000")
    assert parsed.part == "капот"
    assert parsed.price == 5000


def test_hyphen_in_part_name():
    assert parse("к20 стекло пер-зад - 5000").part == "стекло пер-зад"
    # Разделитель с пробелами внутри названия: делим по последнему.
    parsed = parse("к20 крыло - левое – 7000")
    assert parsed.part == "крыло - левое"
    assert parsed.price == 7000


def test_return_word_case_insensitive():
    assert parse("ВОЗВРАТ к20 капот - 100").is_return
    assert parse("Возврат к20 капот - 100").is_return


def test_part_keeps_user_text():
    assert parse("к20 Капот С Обшивкой - 100").part == "Капот С Обшивкой"
    assert part_key("Капот   С обшивкой") == part_key("капот с ОБШИВКОЙ")


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("бмв капот - 5000", "Неизвестная марка"),
        ("к20 капот - 0", "больше нуля"),
        ("к20 капот - абв", "Неверная цена"),
        ("к20 капот - -500", "Неверная цена"),
        ("к20 капот - 12.5", "Неверная цена"),
        ("к20 капот - ", "Не найдена цена"),
        ("к20 капот 5000", "Не найдена цена"),
        ("к20 капот-5000", "Не найдена цена"),
        ("к20 - 5000", "Не указана запчасть"),
        ("с - 5000", "код машины"),
        ("с ТКЕ - 5000", "Не указана запчасть"),
        ("возврат - 5000", "Не указана марка"),
    ],
)
def test_errors(text, message):
    with pytest.raises(ParseError, match=message):
        parse(text)


def test_unknown_car_not_created():
    with pytest.raises(ParseError):
        parse_line("нива капот - 100", CARS)
    assert "нива" not in CARS
