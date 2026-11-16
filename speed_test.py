#!/usr/bin/env python3
"""Консольный замер скорости скачивания последовательными HTTP-запросами."""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

# 1 МБ = 10^6 байт, 1 Мбит = 10^6 бит (десятичные единицы, как в сетях).
BYTES_PER_MB = 1_000_000
BITS_PER_MBIT = 1_000_000
DEFAULT_COUNT = 10
DEFAULT_TIMEOUT = 60.0
USER_AGENT = "internet-speed-test/1.0 (+https://github.com/unnamed00bas/internet-speed-test)"


@dataclass(frozen=True)
class RequestResult:
    """Результат одного успешного запроса."""

    number: int
    size_bytes: int
    elapsed_seconds: float


class DownloadError(Exception):
    """Ошибка сети, HTTP или таймаут при загрузке URL."""


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Замеряет скорость скачивания: делает несколько последовательных "
            "запросов к URL, дожидается полного тела ответа и считает "
            "среднее время, общий объём и скорость."
        )
    )
    parser.add_argument(
        "url",
        help="Адрес, к которому стучаться (например, тяжёлая картинка).",
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        metavar="N",
        help=f"Число последовательных запросов (по умолчанию {DEFAULT_COUNT}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SEC",
        help=f"Таймаут одного запроса в секундах (по умолчанию {DEFAULT_TIMEOUT:g}).",
    )
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("число запросов (-n/--count) должно быть не меньше 1")
    if args.timeout <= 0:
        parser.error("таймаут (--timeout) должен быть больше 0")
    return args


def download_once(url: str, timeout: float) -> int:
    """Скачивает URL целиком и возвращает размер тела в байтах."""
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        # HTTPError — одновременно ответ, его нужно закрыть.
        status = exc.code
        reason = exc.reason
        try:
            exc.close()
        except Exception:
            pass
        raise DownloadError(f"HTTP {status} {reason} для {url}") from exc
    except urllib.error.URLError as exc:
        reason = exc.reason
        message = str(reason) if reason is not None else str(exc)
        lowered = message.lower()
        if "timed out" in lowered or "timeout" in lowered:
            raise DownloadError(
                f"Истёк таймаут {timeout:g} с при запросе {url}"
            ) from exc
        raise DownloadError(f"Ошибка сети при запросе {url}: {message}") from exc
    except TimeoutError as exc:
        raise DownloadError(
            f"Истёк таймаут {timeout:g} с при запросе {url}"
        ) from exc
    except ValueError as exc:
        raise DownloadError(f"Некорректный URL: {url}") from exc
    return len(body)


def run_requests(url: str, count: int, timeout: float) -> list[RequestResult]:
    """Выполняет count последовательных загрузок и печатает строку по каждому."""
    results: list[RequestResult] = []
    for number in range(1, count + 1):
        started = time.perf_counter()
        size_bytes = download_once(url, timeout)
        elapsed = time.perf_counter() - started
        result = RequestResult(number, size_bytes, elapsed)
        results.append(result)
        print(
            f"№ {result.number}: {result.size_bytes} байт, "
            f"{result.elapsed_seconds:.3f} с",
            flush=True,
        )
    return results


def total_bytes(results: Iterable[RequestResult]) -> int:
    return sum(item.size_bytes for item in results)


def total_seconds(results: Iterable[RequestResult]) -> float:
    return sum(item.elapsed_seconds for item in results)


def average_seconds(results: Sequence[RequestResult]) -> float:
    if not results:
        return 0.0
    return total_seconds(results) / len(results)


def speed_mb_per_s(size_bytes: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return (size_bytes / BYTES_PER_MB) / elapsed_seconds


def speed_mbit_per_s(size_bytes: int, elapsed_seconds: float) -> float:
    if elapsed_seconds <= 0:
        return 0.0
    return (size_bytes * 8 / BITS_PER_MBIT) / elapsed_seconds


def print_summary(results: Sequence[RequestResult]) -> None:
    downloaded = total_bytes(results)
    elapsed = total_seconds(results)
    print("---")
    print(f"Среднее время запроса: {average_seconds(results):.3f} с")
    print(f"Всего скачано: {downloaded / BYTES_PER_MB:.2f} МБ")
    print(
        "Скорость: "
        f"{speed_mbit_per_s(downloaded, elapsed):.2f} Мбит/с "
        f"({speed_mb_per_s(downloaded, elapsed):.2f} МБ/с)"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        results = run_requests(args.url, args.count, args.timeout)
    except DownloadError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    print_summary(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
