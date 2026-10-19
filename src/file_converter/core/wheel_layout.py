"""Pure wheel geometry shared by paint, input and deterministic screenshots."""

import math
from dataclasses import dataclass

SIZE = 442
CENTER = SIZE / 2
INNER = 80
OUTER = 196
RIM = 205


@dataclass(frozen=True)
class Slice:
    operation: object
    availability: object


def slices_for(catalog, wheel, items, tools):
    return tuple(Slice(op, op.availability(items, tools)) for op in catalog if op.wheel == wheel and op.applies_to(items))


def hit_test(x, y, count):
    dx, dy = x - CENTER, y - CENTER
    distance = math.hypot(dx, dy)
    if not count or distance < INNER or distance > RIM:
        return -1
    angle = (math.degrees(math.atan2(dx, -dy)) + 360 / count / 2) % 360
    return int(angle / (360 / count)) % count


def label_center(index, count, radius=139):
    angle = 2 * math.pi * index / count
    return CENTER + radius * math.sin(angle), CENTER - radius * math.cos(angle)
