def format_caption(file_name, size, language="Hindi/English"):
    size_mb = round(size / (1024 * 1024), 2)
    return (
        f"🎬 *{file_name}*\n"
        f"📦 Size: {size_mb} MB\n"
        f"🗣️ Language: {language}\n"
        f"📥 Download Now!"
    )