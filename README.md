# blog

DemensDeum blog sources and publishing tools for [RustyBlogger](https://zefir1990.space).

## Publish

```bash
PYTHONIOENCODING=utf-8 python3 compileAndUpload.py <post-slug>
```

Configure `RUSTY_BLOGGER_SITE_URL` and `RUSTY_BLOGGER_POST_EDITOR_KEY` in `.env`.

Media is referenced as `/media/<filename>`; copy media files to the server's media directory.
