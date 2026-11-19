Blog posts must be with txt extension in src directory
Blog posts text is extended blog format
To make upload use "PYTHONIOENCODING=utf-8 python3 compileAndUpload.py [blog post filename without txt extension]
Blog post must be in utf-8
Post category must be software or notes
Category software is used when it is post about presenting new software
Links must be from new line
Posts in src directory must be in russian language by default
Russian grammar must be correct
Fall24-October10 is format type, this is must not be changed to anything else
Publishing uses the RustyBlogger posts CRUD API; set RUSTY_BLOGGER_SITE_URL and RUSTY_BLOGGER_POST_EDITOR_KEY in .env
Media files are referenced as /media/<filename>; keep them in the media directory
Post structure must be:
Format: Fall24-October10
Language: ru
Title: <Title in russian>
Slug: <blog post slug in english>
Categories: software|notes
<Post text>

Code block format as is without language specification:
<pre><code>
print("Hello World")
</code></pre>