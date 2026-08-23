import discord

async def create_promotion_thread(dest_message: discord.Message, original_message: discord.Message, reaction_count: int, image_urls: list[str]):
    """
    昇格先の転送メッセージに対してスレッドを作成し、サムネイルや情報を初期投稿する関数
    
    :param dest_message: 転送先チャンネルに投稿されたメッセージオブジェクト
    :param original_message: 元のメッセージオブジェクト
    :param reaction_count: 達成したリアクション数
    :param image_urls: 添付された画像URLのリスト（1つ以上の前提）
    """
    # 1. スレッド名の決定（元テキストから抽出、またはデフォルト名）
    content_snippet = original_message.content[:20] if original_message.content else "画像投稿"
    thread_name = f"⭐昇格: {original_message.author.display_name} - {content_snippet}"
    
    # スレッド名が100文字を超えないように調整
    thread_name = thread_name[:100]

    try:
        # 2. 転送先メッセージにスレッドを作成
        # auto_archive_duration: 1440 (24時間無通信でアーカイブ)
        thread = await dest_message.create_thread(
            name=thread_name,
            auto_archive_duration=1440
        )

        # 3. スレッド内に投稿する埋め込み（Embed）の作成
        embed = discord.Embed(
            title=f"🎉 昇格通知 (リアクション: {reaction_count})",
            description=original_message.content if original_message.content else "（テキストなし）",
            color=discord.Color.gold()
        )
        
        # 投稿者情報・元のリンクを設定
        embed.set_author(
            name=original_message.author.display_name,
            icon_url=original_message.author.display_avatar.url
        )
        embed.add_field(name="元のメッセージ", value=f"[元の投稿を開く]({original_message.jump_url})", inline=False)

        # 4. サムネイルの設定 (代表画像をサムネイルとして指定)
        if image_urls:
            embed.set_thumbnail(url=image_urls[0])

        # 5. 複数画像（連投まとめ等）がある場合、2枚目以降の画像を概要欄に注記または追加Embedで渡す
        if len(image_urls) > 1:
            more_images_str = "\n".join([f"・[画像 {i+1}]({url})" for i, url in enumerate(image_urls[1:])])
            embed.add_field(name="その他の画像", value=more_images_str, inline=False)

        # 6. スレッドの最初のメッセージ（トピック内容）として送信
        await thread.send(embed=embed)

    except discord.HTTPException as e:
        print(f"スレッド作成エラー: {e}")
