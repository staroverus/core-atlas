import os
import re
import io
import gc
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(page_title="Генератор фотоатласа керна", layout="wide", page_icon="🪨")

st.title("🪨 Автоматический генератор фотоатласа керна")
st.markdown("Сборка пометровых PDF-альбомов высокого разрешения по 4 метра на страницу.")

# Боковая панель параметров
with st.sidebar:
    st.header("Параметры скважины")
    well_name = st.text_input("Номер скважины", value="C-KBK26-011-1")
    layout_mode = st.radio("Формат альбома:", ("Вертикальный (Книжный)", "Горизонтальный (Альбомный)"))
    meters_per_page = st.selectbox("Метров на страницу:", [4, 2, 5, 6], index=0)

uploaded_files = st.file_uploader(
    "Загрузите фотографии ящиков (например: 0-6.jpg, 6-12.jpg ... до 200 м):",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True
)

def get_cyrillic_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def parse_interval(filename):
    matches = re.findall(r'\d+', filename)
    if len(matches) >= 2:
        return int(matches[0]), int(matches[1])
    return 999999, 999999

if uploaded_files:
    sorted_files = sorted(uploaded_files, key=lambda f: parse_interval(f.name)[0])
    first_m = parse_interval(sorted_files[0].name)[0]
    last_m = parse_interval(sorted_files[-1].name)[1]
    
    st.info(f"Загружено снимков: **{len(sorted_files)} шт.** | Распознан ствол: **от {first_m}.0 до {last_m}.0 м**")
    
    if st.button("🚀 Собрать готовый PDF", type="primary"):
        progress = st.progress(0)
        status = st.empty()
        
        status.text("Нарезка интервалов керна...")
        
        y_slices_6 = [
            (0.052, 0.138), (0.194, 0.280), (0.334, 0.422),
            (0.510, 0.605), (0.658, 0.745), (0.805, 0.890)
        ]
        y_slices_2 = [(0.065, 0.275), (0.375, 0.580)]
        
        meter_list = []
        try:
            for i, file_obj in enumerate(sorted_files):
                start_d, end_d = parse_interval(file_obj.name)
                n_rows = end_d - start_d
                slices = y_slices_2 if n_rows == 2 else y_slices_6
                
                # КРИТИЧЕСКИ ВАЖНО: сброс курсора файла в начало перед повторным чтением
                file_obj.seek(0)
                
                img = Image.open(file_obj)
                w, h = img.size
                x1, x2 = int(w * 0.04), int(w * 0.94)
                
                for r in range(min(n_rows, len(slices))):
                    depth = start_d + r
                    y1 = int(slices[r][0] * h)
                    y2 = int(slices[r][1] * h)
                    crop = img.crop((x1, y1, x2, y2))
                    meter_list.append((depth, crop))
                    
                img.close()
                progress.progress((i + 1) / (len(sorted_files) * 2))
                
            status.text("Формирование страниц альбома с крупной оцифровкой...")
            
            font_title = get_cyrillic_font(52, bold=True)
            font_sub = get_cyrillic_font(30, bold=False)
            font_hdr = get_cyrillic_font(32, bold=True)
            font_major = get_cyrillic_font(36, bold=True)
            font_half = get_cyrillic_font(30, bold=True)
            font_minor = get_cyrillic_font(26, bold=False)
            
            pdf_pages = []
            total_meters = len(meter_list)
            total_pages = (total_meters + meters_per_page - 1) // meters_per_page
            
            for p_idx in range(total_pages):
                batch = meter_list[p_idx * meters_per_page : (p_idx + 1) * meters_per_page]
                
                # --- ВЕРТИКАЛЬНЫЙ РЕЖИМ ---
                if "Вертикальный" in layout_mode:
                    PAGE_W, PAGE_H = 2480, 3508
                    page = Image.new("RGB", (PAGE_W, PAGE_H), color=(248, 250, 252))
                    draw = ImageDraw.Draw(page)
                    
                    draw.rectangle([0, 0, PAGE_W, 220], fill=(24, 32, 47))
                    draw.text((90, 50), f"СКВАЖИНА {well_name} — ВЕРТИКАЛЬНЫЙ КАРОТАЖ КЕРНА", font=font_title, fill=(255, 255, 255))
                    draw.text((90, 130), f"Интервал: {batch[0][0]}.0 — {batch[-1][0] + 1}.0 м | Сверху вниз (от устья) | Лист {p_idx + 1} из {total_pages}", font=font_sub, fill=(195, 205, 220))
                    
                    col_w = int((PAGE_W - 220) / meters_per_page)
                    M_H, M_W = 2500, int(col_w * 0.55)
                    y_top = 380
                    
                    for c_idx, (depth, crop) in enumerate(batch):
                        col_x = 110 + c_idx * col_w
                        card_w = col_w - 20
                        
                        draw.rectangle([col_x, y_top - 80, col_x + card_w, y_top + M_H + 70], fill=(255, 255, 255), outline=(218, 225, 233), width=2)
                        draw.rectangle([col_x, y_top - 80, col_x + card_w, y_top - 15], fill=(238, 242, 248))
                        draw.text((col_x + 35, y_top - 62), f"ИНТЕРВАЛ {depth}.0 — {depth+1}.0 м", font=font_hdr, fill=(20, 30, 48))
                        
                        ruler_x = col_x + int(card_w * 0.32)
                        core_x = ruler_x + 20
                        draw.line([(ruler_x, y_top), (ruler_x, y_top + M_H)], fill=(100, 116, 139), width=4)
                        
                        for dm in range(11):
                            tick_y = y_top + int(dm * (M_H / 10.0))
                            val = depth + dm * 0.1
                            if dm in (0, 10):
                                draw.line([(ruler_x - 38, tick_y), (ruler_x, tick_y)], fill=(15, 23, 42), width=4)
                                lbl = f"{val:.1f} м"
                                bbox = draw.textbbox((0, 0), lbl, font=font_major)
                                draw.text((ruler_x - 38 - (bbox[2]-bbox[0]) - 12, tick_y - (bbox[3]-bbox[1])//2 - 4), lbl, font=font_major, fill=(15, 23, 42))
                                draw.line([(ruler_x, tick_y), (core_x + M_W, tick_y)], fill=(148, 163, 184), width=2)
                            elif dm == 5:
                                draw.line([(ruler_x - 26, tick_y), (ruler_x, tick_y)], fill=(51, 65, 85), width=3)
                                lbl = f"{val:.1f} м"
                                bbox = draw.textbbox((0, 0), lbl, font=font_half)
                                draw.text((ruler_x - 26 - (bbox[2]-bbox[0]) - 10, tick_y - (bbox[3]-bbox[1])//2 - 3), lbl, font=font_half, fill=(30, 41, 59))
                            else:
                                draw.line([(ruler_x - 16, tick_y), (ruler_x, tick_y)], fill=(100, 116, 139), width=2)
                                lbl = f"{val:.1f}"
                                bbox = draw.textbbox((0, 0), lbl, font=font_minor)
                                draw.text((ruler_x - 16 - (bbox[2]-bbox[0]) - 8, tick_y - (bbox[3]-bbox[1])//2 - 3), lbl, font=font_minor, fill=(100, 116, 139))
                                
                        vert_img = crop.transpose(Image.Transpose.ROTATE_270).resize((M_W, M_H), Image.Resampling.LANCZOS)
                        page.paste(vert_img, (core_x, y_top))
                        draw.rectangle([core_x - 1, y_top - 1, core_x + M_W + 1, y_top + M_H + 1], outline=(71, 85, 105), width=3)
                
                # --- ГОРИЗОНТАЛЬНЫЙ РЕЖИМ ---
                else:
                    PAGE_W, PAGE_H = 3508, 2480
                    page = Image.new("RGB", (PAGE_W, PAGE_H), color=(248, 250, 252))
                    draw = ImageDraw.Draw(page)
                    
                    draw.rectangle([0, 0, PAGE_W, 200], fill=(24, 32, 47))
                    draw.text((100, 45), f"СКВАЖИНА {well_name} — ГОРИЗОНТАЛЬНЫЙ ФОТОАТЛАС КЕРНА", font=font_title, fill=(255, 255, 255))
                    draw.text((100, 115), f"Интервал: {batch[0][0]}.0 — {batch[-1][0] + 1}.0 м | Слева направо (от устья) | Лист {p_idx + 1} из {total_pages}", font=font_sub, fill=(195, 205, 220))
                    
                    row_pitch = int((PAGE_H - 250) / meters_per_page)
                    card_h = row_pitch - 45
                    CORE_W = 2750
                    CORE_H = int(card_h * 0.55)
                    
                    for r_idx, (depth, crop) in enumerate(batch):
                        card_y = 240 + r_idx * row_pitch
                        card_x = 90
                        card_w = PAGE_W - 180
                        
                        draw.rectangle([card_x, card_y, card_x + card_w, card_y + card_h], fill=(255, 255, 255), outline=(218, 225, 233), width=2)
                        
                        badge_w = 420
                        draw.rectangle([card_x + 20, card_y + 15, card_x + badge_w, card_y + card_h - 15], fill=(238, 242, 248), outline=(205, 215, 228), width=2)
                        draw.text((card_x + 55, card_y + int(card_h * 0.25)), "ИНТЕРВАЛ", font=font_sub, fill=(100, 116, 139))
                        draw.text((card_x + 50, card_y + int(card_h * 0.45)), f"{depth}.0 — {depth+1}.0 м", font=font_major, fill=(20, 30, 48))
                        
                        core_x = card_x + 480
                        core_y = card_y + int(card_h * 0.35)
                        ruler_y = core_y - 12
                        draw.line([(core_x, ruler_y), (core_x + CORE_W, ruler_y)], fill=(100, 116, 139), width=4)
                        
                        for dm in range(11):
                            tick_x = core_x + int(dm * (CORE_W / 10.0))
                            val = depth + dm * 0.1
                            if dm in (0, 10):
                                draw.line([(tick_x, ruler_y), (tick_x, ruler_y - 36)], fill=(15, 23, 42), width=4)
                                lbl = f"{val:.1f} м"
                                bbox = draw.textbbox((0, 0), lbl, font=font_major)
                                lbl_w = bbox[2] - bbox[0]
                                off_x = 0 if dm == 0 else (-lbl_w if dm == 10 else -lbl_w // 2)
                                draw.text((tick_x + off_x, ruler_y - 36 - 42), lbl, font=font_major, fill=(15, 23, 42))
                                draw.line([(tick_x, core_y), (tick_x, core_y + CORE_H)], fill=(148, 163, 184), width=2)
                            elif dm == 5:
                                draw.line([(tick_x, ruler_y), (tick_x, ruler_y - 25)], fill=(51, 65, 85), width=3)
                                lbl = f"{val:.1f} м"
                                bbox = draw.textbbox((0, 0), lbl, font=font_half)
                                draw.text((tick_x - (bbox[2]-bbox[0]) // 2, ruler_y - 25 - 36), lbl, font=font_half, fill=(30, 41, 59))
                            else:
                                draw.line([(tick_x, ruler_y), (tick_x, ruler_y - 16)], fill=(100, 116, 139), width=2)
                                lbl = f"{val:.1f}"
                                bbox = draw.textbbox((0, 0), lbl, font=font_minor)
                                draw.text((tick_x - (bbox[2]-bbox[0]) // 2, ruler_y - 16 - 32), lbl, font=font_minor, fill=(100, 116, 139))
                                
                        horiz_img = crop.resize((CORE_W, CORE_H), Image.Resampling.LANCZOS)
                        page.paste(horiz_img, (core_x, core_y))
                        draw.rectangle([core_x - 1, core_y - 1, core_x + CORE_W + 1, core_y + CORE_H + 1], outline=(71, 85, 105), width=3)
                
                pdf_pages.append(page)
                progress.progress(0.5 + (p_idx + 1) / (total_pages * 2))
                
            status.text("Оптимизация и сборка PDF...")
            pdf_buf = io.BytesIO()
            pdf_pages[0].save(
                pdf_buf, format="PDF", save_all=True, append_images=pdf_pages[1:], resolution=300.0, quality=95
            )
            pdf_buf.seek(0)
            
            # Очистка объектов из оперативной памяти
            del pdf_pages
            del meter_list
            gc.collect()
            
            status.empty()
            progress.empty()
            st.success(f"Альбом готов! Сформировано {total_pages} страниц (300 DPI).")
            
            mode_tag = "Vert" if "Вертикальный" in layout_mode else "Horiz"
            st.download_button(
                label="📥 Скачать готовый PDF-альбом",
                data=pdf_buf,
                file_name=f"{well_name}_{mode_tag}_{first_m}-{last_m}m.pdf",
                mime="application/pdf",
                type="primary"
            )
        except Exception as e:
            status.empty()
            progress.empty()
            st.error(f"Произошла ошибка при обработке: {e}")
