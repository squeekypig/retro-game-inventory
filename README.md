# RetroVault — Retro Game Inventory

Identify retro game cartridges, boxes, and discs using AI and manage your collection.

## Setup

1. **Set your Anthropic API key:**
   ```
   set ANTHROPIC_API_KEY=your-api-key-here
   ```

2. **Install dependencies** (first time only):
   ```
   python -m pip install fastapi "uvicorn[standard]" anthropic python-multipart
   ```

3. **Start the server:**
   ```
   start.bat
   ```
   or:
   ```
   python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. Open **http://localhost:8000** in your browser.

## Features

- **Photo identification** — Take or upload a photo of a cartridge, box, or disc. Claude AI identifies the game, platform, and release year.
- **Manual entry** — Add games without a photo.
- **Filter & sort** by platform, title, year, or value.
- **Owned / Wishlist** — Track what you have and what you want.
- **Estimated value** — Log market values for your collection.

## Usage Tips

- Works best with clear, well-lit photos showing the label or box art.
- You can edit any auto-identified field before saving.
- Use from your phone by accessing `http://<your-pc-ip>:8000` on the same network.
