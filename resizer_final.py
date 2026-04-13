import os, threading, queue, io, subprocess, sys
try:
    import customtkinter as ctk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

try:
    from PIL import Image, ImageOps, ImageFilter
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    from PIL import Image, ImageOps, ImageFilter

from tkinter import filedialog, messagebox

# --- CONFIGURATION ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

GREEN, BG_DARK, BORDER = "#1DB954", "#0D1117", "#30363D"
BG_CARD, BG_INPUT = "#161B22", "#1C2333"
TEXT_MAIN, TEXT_MUTED, TEXT_DIM = "#F0F6FC", "#8B949E", "#484F58"

# ══════════════════════════════════════════════════════════════════════════
#  CORE IMAGE ENGINE (Original Logic Maintained)
# ══════════════════════════════════════════════════════════════════════════

def make_tiled_bg(img, target_w, target_h, tile_size=500):
    cx = max(0, (img.width - tile_size) // 2)
    cy = max(0, (img.height - tile_size) // 2)
    s = img.crop((cx, cy, min(img.width, cx + tile_size), min(img.height, cy + tile_size)))
    if s.width < 10 or s.height < 10: return Image.new("RGB", (target_w, target_h), (30, 30, 30))
    tw, th = s.width, s.height
    tile = Image.new("RGB", (tw * 2, th * 2))
    tile.paste(s, (0, 0))
    tile.paste(ImageOps.mirror(s), (tw, 0))
    tile.paste(ImageOps.flip(s), (0, th))
    tile.paste(ImageOps.mirror(ImageOps.flip(s)), (tw, th))
    tile = tile.filter(ImageFilter.GaussianBlur(radius=2))
    bg = Image.new("RGB", (target_w, target_h))
    for x in range(0, target_w, tile.width):
        for y in range(0, target_h, tile.height): bg.paste(tile, (x, y))
    return bg

def place_contain(img, target_w, target_h):
    bg = make_tiled_bg(img, target_w, target_h)
    fg = img.copy()
    fg.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
    bg.paste(fg, ((target_w - fg.width) // 2, (target_h - fg.height) // 2))
    return bg

def place_cover(img, target_w, target_h):
    src_r, tgt_r = img.width/img.height, target_w/target_h
    new_w, new_h = (target_w, round(target_w/src_r)) if src_r <= tgt_r else (round(target_h*src_r), target_h)
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    l, t = (new_w - target_w)//2, (new_h - target_h)//2
    return resized.crop((l, t, l + target_w, t + target_h))

def smart_crop(img, target_w, target_h):
    sr, tr = img.width/img.height, target_w/target_h
    nw, nh = (target_w, round(target_w/sr)) if sr <= tr else (round(target_h*sr), target_h)
    res = img.resize((nw, nh), Image.Resampling.LANCZOS)
    bbox = res.convert("L").filter(ImageFilter.FIND_EDGES).getbbox()
    cx, cy = (bbox[0]+bbox[2])//2 if bbox else nw//2, (bbox[1]+bbox[3])//2 if bbox else nh//2
    lx, ly = max(0, min(cx-target_w//2, nw-target_w)), max(0, min(cy-target_h//2, nh-target_h))
    return res.crop((lx, ly, lx+target_w, ly+target_h))

def smart_save(img, path, fmt, max_bytes):
    if fmt.upper() in ("PNG", "TIFF"):
        img.save(path, fmt.upper()); return os.path.getsize(path) <= max_bytes, os.path.getsize(path)
    lo, hi, best_q = 30, 95, 85
    for _ in range(8):
        mid = (lo + hi) // 2
        buf = io.BytesIO()
        img.save(buf, fmt.upper(), quality=mid, optimize=True)
        if buf.tell() <= max_bytes: best_q, lo = mid, mid + 1
        else: hi = mid - 1
    img.save(path, fmt.upper(), quality=best_q, optimize=True)
    return os.path.getsize(path) <= max_bytes, os.path.getsize(path)

# ══════════════════════════════════════════════════════════════════════════
#  GUI & WORKER (Mac Compatible)
# ══════════════════════════════════════════════════════════════════════════

msg_queue = queue.Queue()

def worker(inp, tw, th, out, mode, fmt, mb):
    files = [f for f in os.listdir(inp) if f.lower().endswith(('.jpg','.jpeg','.png','.webp','.tiff','.bmp'))]
    if not files: msg_queue.put(("done", 0)); return
    for i, fn in enumerate(files):
        try:
            with Image.open(os.path.join(inp, fn)) as im:
                im = im.convert("RGB")
                if mode == "contain": res = place_contain(im, tw, th)
                elif mode == "cover": res = place_cover(im, tw, th)
                else: res = smart_crop(im, tw, th)
                
                out_path = os.path.join(out, f"{os.path.splitext(fn)[0]}_resized.{'jpg' if fmt=='jpeg' else fmt}")
                ok, size = smart_save(res, out_path, fmt, mb)
                msg_queue.put(("progress", i+1, len(files), fn, round(size/1024), ok))
        except Exception as e: msg_queue.put(("error", fn, str(e)))
    msg_queue.put(("done", len(files)))

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Siar Digital Resizer")
        self.configure(fg_color=BG_DARK)
        # Mac Centering
        ww, wh = 600, 850
        self.geometry(f"{ww}x{wh}+{(self.winfo_screenwidth()-ww)//2}+{(self.winfo_screenheight()-wh)//2}")
        
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=BG_DARK)
        self.scroll.pack(fill="both", expand=True)
        self._build_ui()
        self.after(100, self.poll_queue)

    def _build_ui(self):
        # Header
        h = ctk.CTkFrame(self.scroll, fg_color=BG_CARD, corner_radius=12, border_color=BORDER, border_width=1)
        h.pack(fill="x", padx=16, pady=16)
        ctk.CTkLabel(h, text="Siar Digital Resizer", font=("Segoe UI", 24, "bold"), text_color=TEXT_MAIN).pack(pady=(15,2))
        ctk.CTkLabel(h, text="Created by Asif Nawaz", font=("Segoe UI", 12), text_color=GREEN).pack(pady=(0,15))

        # Folder
        self.folder_var = ctk.StringVar()
        f_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        f_row.pack(fill="x", padx=20, pady=10)
        ctk.CTkEntry(f_row, textvariable=self.folder_var, placeholder_text="Input folder...", height=40, fg_color=BG_INPUT).pack(side="left", fill="x", expand=True, padx=(0,10))
        ctk.CTkButton(f_row, text="Browse", fg_color=GREEN, width=100, command=lambda: self.folder_var.set(filedialog.askdirectory())).pack(side="left")

        # Start Button
        self.start_btn = ctk.CTkButton(self.scroll, text="▶ START PROCESSING", font=("Segoe UI", 16, "bold"), fg_color=GREEN, height=55, command=self.start)
        self.start_btn.pack(fill="x", padx=20, pady=20)
        
        # Progress & Status
        self.p_bar = ctk.CTkProgressBar(self.scroll, progress_color=GREEN)
        self.p_bar.set(0)
        self.p_bar.pack(fill="x", padx=20, pady=10)
        self.status_var = ctk.StringVar(value="Ready to process...")
        ctk.CTkLabel(self.scroll, textvariable=self.status_var, font=("Segoe UI", 11), text_color=TEXT_MUTED).pack(padx=20)

    def start(self):
        f = self.folder_var.get().strip()
        if not f or not os.path.isdir(f):
            messagebox.showwarning("Error", "Select folder first!"); return
        out = os.path.join(f, "Siar_Output")
        os.makedirs(out, exist_ok=True)
        self.start_btn.configure(state="disabled", text="Processing...")
        threading.Thread(target=worker, args=(f, 850, 1280, out, "contain", "webp", 1500*1024), daemon=True).start()

    def poll_queue(self):
        try:
            while True:
                m = msg_queue.get_nowait()
                if m[0] == "progress":
                    self.p_bar.set(m[1]/m[2])
                    self.status_var.set(f"Processing: {m[3]} ({m[4]} KB)")
                elif m[0] == "done":
                    self.p_bar.set(1)
                    self.status_var.set(f"Completed! {m[1]} images saved.")
                    self.start_btn.configure(state="normal", text="▶ START PROCESSING")
                    messagebox.showinfo("Success", "Process Complete!")
        except: pass
        self.after(100, self.poll_queue)

if __name__ == "__main__":
    App().mainloop()
