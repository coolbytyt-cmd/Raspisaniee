import flet as ft
import json
import os
import re
from datetime import date, datetime, timedelta

CACHE_FILE = "mesh_college_cache.json"

def plural_lessons(n):
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} урок"
    elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return f"{n} урока"
    return f"{n} уроков"

def plural_minutes(n):
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} минута"
    elif 2 <= n % 10 <= 4 and not (12 <= n % 100 <= 14):
        return f"{n} минуты"
    return f"{n} минут"

def time_to_minutes(t_str):
    try:
        h, m = map(int, t_str.strip().split(":"))
        return h * 60 + m
    except Exception:
        return None

def parse_day_text(raw_text):
    raw_text = (raw_text or "").replace("\xa0", " ")
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    time_re = re.compile(r"(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})")
    single_time_re = re.compile(r"^(\d{1,2}:\d{2})$")

    blocks = []
    cur = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = time_re.search(line)
        if m:
            if cur:
                blocks.append(cur)
            cur = {"start": m.group(1), "end": m.group(2), "lines": []}
            rem = time_re.sub("", line).strip(" •|-")
            if rem:
                cur["lines"].append(rem)
            i += 1
            continue

        m1 = single_time_re.match(line)
        if m1 and i + 1 < len(lines) and single_time_re.match(lines[i + 1]):
            if cur:
                blocks.append(cur)
            cur = {"start": m1.group(1), "end": lines[i + 1], "lines": []}
            i += 2
            continue

        if cur is not None:
            cur["lines"].append(line)
        i += 1

    if cur:
        blocks.append(cur)

    lessons = []
    skip_exact = {"очно", "дистанционно", "дистант", "лекция", "практика", "семинар", "лабораторная", "зачет", "экзамен"}
    for b in blocks:
        subject, room, hw_lines, raw_marks = "", "", [], []
        for l in b["lines"]:
            low = l.lower().strip()
            if low.startswith(("перемена", "окно", "обед")) or low in skip_exact:
                continue
            if re.match(r"^(?:занятие|пара|урок)\s*[№#]?\s*\d+\s*$", low):
                continue

            mm = re.match(r"^(?:оценка\s*)?([2-5])(?:\s*[xх×*]\s*(\d+))?$", l.strip(), re.IGNORECASE)
            if mm:
                raw_marks.append({"val": mm.group(1), "weight": mm.group(2) or "1"})
                continue

            rm = re.search(r"(?:ауд\.?|каб\.?|аудитория|кабинет)\s*([№#]?\s*[A-Za-zА-Яа-я0-9\-/]+)", l, re.IGNORECASE)
            if rm:
                room = f"Ауд. {rm.group(1).strip()}"
                continue

            if not subject and len(l) > 2:
                subject = re.sub(r"^(?:занятие|пара|урок)\s*[№#]?\s*\d+\s*[•|\-–—:]?\s*", "", l, flags=re.IGNORECASE).strip()
                continue

            cleaned_hw = re.sub(r"^(?:дз|домашнее задание)\s*:?\s*", "", l, flags=re.IGNORECASE).strip()
            if cleaned_hw:
                hw_lines.append(cleaned_hw)

        if subject:
            lessons.append({
                "start": b["start"],
                "end": b["end"],
                "subject": subject,
                "room": room if room else "Аудитория не указана",
                "homework": "\n".join(hw_lines),
                "marks": raw_marks
            })
    return lessons


def main(page: ft.Page):
    page.title = "Rасписание"
    page.bgcolor = "#141417"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = ft.padding.only(top=36, left=14, right=14, bottom=14)

    cache = {"updated_at": "", "schedule": {}}
    saved_client_cache = page.client_storage.get("roy_mesh_cache")
    if saved_client_cache:
        cache = saved_client_cache
    elif os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
                page.client_storage.set("roy_mesh_cache", cache)
        except Exception:
            pass

    today = date.today()
    selected_date = today + timedelta(days=1) if today.weekday() == 6 else today
    week_monday = selected_date - timedelta(days=selected_date.weekday())

    title_lbl = ft.Text("Сегодня", size=20, weight=ft.FontWeight.BOLD, color="#FFFFFF")
    count_lbl = ft.Container(
        content=ft.Text("0 уроков", size=12, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
        bgcolor="#26262B",
        border=ft.border.all(1, "#3E3E45"),
        border_radius=11,
        padding=ft.padding.symmetric(horizontal=10, vertical=4),
    )

    week_row = ft.Row(spacing=6, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    cards_col = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)

    def build_mark_badge(val, weight):
        colors = {
            "5": ("#2ECC71", "#7DF5AF"),
            "4": ("#3498DB", "#87CEFA"),
            "3": ("#F39C12", "#FFD26E"),
            "2": ("#E74C3C", "#FF9187"),
        }
        bg, border = colors.get(str(val), ("#555555", "#AAAAAA"))
        has_w = str(weight) not in ("", "0", "1")
        items = [
            ft.Container(
                content=ft.Text(str(val), size=13, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                width=24,
                height=24,
                bgcolor=bg,
                border=ft.border.all(1.5, border),
                border_radius=8,
                alignment=ft.alignment.center,
            )
        ]
        if has_w:
            items.append(ft.Text(str(weight), size=11, weight=ft.FontWeight.W_900, color=border))
        return ft.Row(items, spacing=2, vertical_alignment=ft.CrossAxisAlignment.END)

    def create_lesson_card(idx, item, is_sat):
        hw_text = (item.get("homework") or "").strip() or "Домашнее задание не задано"
        has_cdz = bool(item.get("cdz_url")) or ("цдз" in hw_text.lower())

        hw_panel_items = [
            ft.Text("Домашнее задание:", size=11, weight=ft.FontWeight.BOLD, color="#A0A0A8"),
            ft.Text(hw_text, size=13, color="#F2F2F5", selectable=True),
        ]
        if has_cdz:
            target_url = item.get("cdz_url") or "https://mos.ru"
            hw_panel_items.append(
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Перейти на ЦДЗ →",
                            bgcolor="#383840",
                            color="#FFFFFF",
                            height=30,
                            on_click=lambda e, u=target_url: page.launch_url(u),
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                )
            )

        hw_container = ft.Container(
            content=ft.Column(hw_panel_items, spacing=6),
            bgcolor="#2A2A30",
            border=ft.border.all(1, "#404048"),
            border_radius=12,
            padding=12,
            margin=ft.margin.only(top=10),
            visible=False,
        )

        subj_text = ft.Text(
            item.get("subject", "Предмет"),
            size=15,
            weight=ft.FontWeight.BOLD,
            color="#FFFFFF",
            max_lines=2,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        def toggle_expand(e):
            hw_container.visible = not hw_container.visible
            subj_text.max_lines = 10 if hw_container.visible else 2
            page.update()

        top_badges = [ft.Text(f"Урок {idx}" if idx > 0 else "Инфо", size=12, weight=ft.FontWeight.BOLD, color="#A0A0A8")]
        for mk in item.get("marks", []):
            top_badges.append(build_mark_badge(mk.get("val"), mk.get("weight", "1")))
        top_badges.append(ft.Container(expand=True))

        room_str = item.get("room", "Аудитория не указана")
        if is_sat and idx > 0:
            top_badges.append(
                ft.Container(
                    content=ft.Text("Дистант", size=11, weight=ft.FontWeight.BOLD, color="#DDF0FF"),
                    bgcolor="#23384D",
                    border=ft.border.all(1, "#4A78A6"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                )
            )
        if not is_sat or (room_str not in ("Аудитория не указана", "Нет данных")):
            top_badges.append(
                ft.Container(
                    content=ft.Text(room_str, size=11, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                    bgcolor="#2F2F36",
                    border=ft.border.all(1, "#484852"),
                    border_radius=8,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                )
            )

        main_row = ft.Row(
            [
                ft.Column(
                    [
                        ft.Text(item.get("start", ""), size=15, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                        ft.Text(item.get("end", ""), size=12, color="#9A9AA2"),
                    ],
                    spacing=2,
                    width=46,
                ),
                ft.Container(width=3, height=44, bgcolor="#E5E5EA", border_radius=2),
                ft.Column(
                    [ft.Row(top_badges, spacing=6), subj_text],
                    spacing=5,
                    expand=True,
                ),
            ],
            spacing=12,
        )

        return ft.Container(
            content=ft.Column([main_row, hw_container], spacing=0),
            bgcolor="#202024",
            border=ft.border.all(1, "#36363E"),
            border_radius=18,
            padding=14,
            on_click=toggle_expand,
        )

    def refresh_ui():
        nonlocal selected_date, week_monday
        days_short = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]
        week_row.controls.clear()

        def shift_week(delta):
            nonlocal selected_date, week_monday
