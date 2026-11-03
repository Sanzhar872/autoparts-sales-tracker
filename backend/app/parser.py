"""Разбор текстовых строк продаж и возвратов. Без обращения к БД."""

import re
from collections.abc import Container
from dataclasses import dataclass

from app.constants import MAX_PRICE, OLD_CAR

RETURN_WORD = "возврат"
# Латинские буквы, похожие на кириллические (после перевода в нижний регистр).
LATIN_TO_CYRILLIC = str.maketrans("acekmoptxybh", "асекмортхувн")
PRICE_SEPARATOR = re.compile(r" [-–—] ")


class ParseError(Exception):
    pass


@dataclass
class ParsedLine:
    is_return: bool
    car: str
    old_car_code: str | None
    part: str
    price: int


def clean(text: str) -> str:
    """Убрать пробелы по краям и схлопнуть повторные."""
    return " ".join(text.split())


def normalize_car(name: str) -> str:
    return name.lower().translate(LATIN_TO_CYRILLIC)


def part_key(part: str) -> str:
    """Ключ сравнения запчастей: без учёта регистра и повторных пробелов."""
    return clean(part).lower()


def parse_price(text: str) -> int:
    digits = re.sub(r"\s", "", text)
    if not digits.isascii() or not digits.isdigit():
        raise ParseError(f"Неверная цена «{text}»: нужно целое число больше нуля")
    price = int(digits)
    if price <= 0:
        raise ParseError("Цена должна быть больше нуля")
    if price > MAX_PRICE:
        raise ParseError("Слишком большая цена")
    return price


def parse_line(text: str, known_cars: Container[str]) -> ParsedLine:
    line = clean(text)
    separators = list(PRICE_SEPARATOR.finditer(line))
    if not separators:
        raise ParseError("Не найдена цена: ожидается «марка запчасть - цена»")
    last = separators[-1]
    left, price_text = line[: last.start()], line[last.end():]
    price = parse_price(price_text)

    words = left.split(" ")
    is_return = words[0].lower() == RETURN_WORD
    if is_return:
        words = words[1:]
    if not words:
        raise ParseError("Не указана марка")

    car = normalize_car(words[0])
    if car not in known_cars:
        raise ParseError(f"Неизвестная марка «{words[0]}»")

    old_car_code = None
    rest = words[1:]
    if car == OLD_CAR:
        if not rest:
            raise ParseError("Для старого завоза укажите код машины: «с <код> <запчасть> - <цена>»")
        old_car_code = rest[0].upper()
        rest = rest[1:]

    part = " ".join(rest)
    if not part:
        raise ParseError("Не указана запчасть")

    return ParsedLine(is_return=is_return, car=car, old_car_code=old_car_code, part=part, price=price)
