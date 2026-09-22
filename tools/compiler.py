#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import re
import difflib
import os
import subprocess
import sys

def askOllama(prompt):
    import requests

    base_url = 'http://localhost:11434'
    endpoint = '/api/generate'

    prompt = prompt.strip()

    payload = {
        "model": "llama3.2", 
        "stream": False,                            
        "prompt": prompt
    }
    response = requests.post(base_url + endpoint, json=payload)
    if response.status_code == 200:
        answer = response.json().get("response")
        if answer[0] == '"':
            answer = answer[1:]
        if answer[-1] == '"':
            answer = answer[0:-1]
        return str(answer)
    else:
        print("ollama error")
        exit(1)
        return None

def separate_latin_and_non_latin(text):
    latin_pattern = re.compile(r'[A-Za-z]+')
    non_latin_pattern = re.compile(r'[^\x00-\x7F]+')

    result = []
    i = 0

    while i < len(text):
        if text[i].isascii() and text[i].isalpha():
            match = latin_pattern.match(text, i)
            if match:
                result.append(match.group())
                i = match.end()
        elif not text[i].isascii():
            match = non_latin_pattern.match(text, i)
            if match:
                result.append(match.group())
                i = match.end()
        else:
            result.append(text[i])
            i += 1

    return ' '.join(result).strip()

def replace_similar_latin_words(text1, text2):
    text1_words = text1.split()
    text2_words = text2.split()
    latin_pattern = re.compile(r'^[a-zA-Z]+$')
    text1_latin_words = [word for word in text1_words if latin_pattern.match(word)]
    result = []
    for word2 in text2_words:
        if latin_pattern.match(word2):
            matches = difflib.get_close_matches(word2.lower(), text1_latin_words, n=1, cutoff=0.3)
            if matches:
                result.append(matches[0])
            else:
                result.append(word2)
        else:
            result.append(word2)
    return ' '.join(result)

parser = argparse.ArgumentParser(description="Wordpress post compiler.")
parser.add_argument("--input", required=True, help="Input file path.")
parser.add_argument("--output", required=True, help="Output file path.")

args = parser.parse_args()
inputFile = args.input
outputFile = args.output

inputFileLines = open(inputFile, "r", encoding="utf-8").readlines()

if len(inputFileLines) < 5:
    print("\
          Post must contains at least 5 lines.\n\
          Format: format code\n\
          Language: post language code\n\
          Title: post title\n\
          Slug: post_slug\n\
          Categories: categories separated by comma\n\
          Post content\
          ")
    exit(1)

supportingFormatCode = "Fall24-October10"

formatCode = inputFileLines[0].strip()[len("Format: "):]

if formatCode != supportingFormatCode:
    print(f"Can't process file with formatCode: \"{formatCode}\", because compiler supports \"{supportingFormatCode}\" only")
    exit(1)

language = inputFileLines[1].strip()[len("Language: "):]
title = inputFileLines[2].strip()
slug = inputFileLines[3].strip()
categories = inputFileLines[4].strip()[len("Categories: "):].split(",")
inputFileLines = inputFileLines[5:]

print(f"Post_title: {title}")
print(f"Slug: {slug}")

if title.startswith("Title: ") == False:
    print("Title line must start with \"Title:\" prefix")
    exit(1)

if slug.startswith("Slug: ") == False:
    print("Slug line must start with \"Slug:\" prefix")
    exit(1)

title = title[len("Title: "):]
slug = slug[len("Slug: "):]

directory = "build"
if not os.path.exists(directory):
    os.mkdir(directory)

outputFileDescriptor = open(outputFile, "w", encoding="utf-8")

state = "text"
codeStateLanguage = "Bash"
previousState = "text"
textBlock = ""
outputText = ""

doNotProcessPrefixes = ["[DO NOT PROCESS LINE]", "<img src=", "[video src="]

googleTranslateEndpoint = "https://translate.googleapis.com/translate_a/single"
googleTranslateImpersonation = "chrome"

def translateWithGoogle(text, source, destination):
    from curl_cffi import requests as curlRequests

    if source == destination or text.strip() == "":
        return text

    parameters = {
        "client": "gtx",
        "sl": source,
        "tl": destination,
        "dt": "t",
        "q": text,
    }

    response = curlRequests.get(
        googleTranslateEndpoint,
        params=parameters,
        impersonate=googleTranslateImpersonation,
        timeout=30
    )

    if response.status_code != 200:
        raise RuntimeError(f"Google Translate returned status {response.status_code}")

    segments = response.json()[0]
    translatedText = "".join(segment[0] for segment in segments if segment and segment[0])

    if translatedText.strip() == "":
        raise RuntimeError("Google Translate returned empty result")

    return translatedText

def translate(text, type, source, destination):
    if any(text.strip().startswith(prefix) for prefix in doNotProcessPrefixes):
        if text.strip().startswith("[DO NOT PROCESS LINE]"):
            return text[len("[DO NOT PROCESS LINE]"):]
        return text
        
    print(f"translate {source} -> {destination} by {type}")
    print(f"text: \"{text}\"")

    if type == "google":
        print(source)
        print(destination)
        outputText = None

        for i in range(0, 10):
            try:
                outputText = translateWithGoogle(text, source, destination)
                break
            except Exception as error:
                print(error)

        if outputText is None:
            print(f"Translation failed for target \"{destination}\" after 10 attempts, source text: \"{text}\"")
            exit(1)

        if outputText.strip().lower().startswith("<h2>") and not outputText.strip().lower().endswith("</h2>"):
            outputText += "</h2>"

        if outputText.strip().lower().startswith("<h3>") and not outputText.strip().lower().endswith("</h3>"):
            outputText += "</h3>"

        outputText = outputText.replace("Ilya", "Ilia")
        return outputText

    elif type == "openai":
        from openai import OpenAI

        client = OpenAI(
            api_key=open("./private/openAI_api_key", "r").read().strip()
        )        
        chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": "Say this is a test",
            }
        ],
        model="gpt-3.5-turbo",
        )
        return chat_completion['choices'][0]['message']['content'].strip()
    
    elif type == "ollama":
        prompt = f"""
            Translate text: \"{text}\" from \"{source}" to \"{destination}". Context is programmer blog. I need only translation, without additional comments from your side, also no additional quotes, so I can copy and paste your output directly into file.       
            """    
        answer = askOllama(prompt)    
        print(answer)
        return answer

codeEscapedSymbols = [
    ("<","&lt;"),
    (">","&gt;"),
    ('"',"&quot;"),
]

def processLine(line, state):
    outputLine = line

    if state == "code":
        for codeEscapedSymbol in codeEscapedSymbols:
            outputLine = outputLine.replace(codeEscapedSymbol[0], codeEscapedSymbol[1])

    return outputLine

def processLink(line):
    outputLine = line.replace("http://", "https://")
    outputLine = outputLine.strip()
    outputLine = f"<a href=\"{outputLine}\" rel=\"noopener\" target=\"_blank\">{outputLine}</a>"

    return outputLine

lastLineIndex = len(inputFileLines) - 1

languageCodes = ["ru", "en", "zh", "de", "ja", "fr", "pt", "hi"]
googleTranslateLanguageCodes = ["ru", "en", "zh-CN", "de", "ja", "fr", "pt", "hi"]
originalLanguageCode = language

def uploadImage(filename):
    filename = filename.strip()
    print(f"Uploading image: {filename}")

    script_path = os.path.join(".", "tools", "mediaUploader.py")

    result = subprocess.run(
        [sys.executable, script_path, filename],
        capture_output=True,
        text=True,
        check=True
    )

    uploaded_path = result.stdout.strip()

    if not uploaded_path:
        print(f"Warning: mediaUploader.py returned empty string for {filename}")
        return filename

    print(f"uploaded_path: {uploaded_path}")

    return uploaded_path

def translateTitle(title):  
    if any(title.startswith(prefix) for prefix in doNotProcessPrefixes):
        if title.startswith("[DO NOT PROCESS LINE]"):
            return title[len("[DO NOT PROCESS LINE]"):]
        return title
          
    output = f"{{:{originalLanguageCode}}}{title}{{:}}"
    for i in range(len(languageCodes)):
        if languageCodes[i] == originalLanguageCode:
            continue
        output += f"{{:{languageCodes[i]}}}"
        output += translate(title, "google", originalLanguageCode, googleTranslateLanguageCodes[i])
        output += "{:}"

    return output.replace("\n"," ")

outputFileDescriptor.write(slug.strip())
outputFileDescriptor.write("\n")
outputFileDescriptor.write(translateTitle(title).strip())
outputFileDescriptor.write("\n")
outputFileDescriptor.write(",".join(categories))
outputFileDescriptor.write("\n")

for languageIndex in range(len(languageCodes)):
    targetLanguageCode = languageCodes[languageIndex]
    outputFileDescriptor.write(f"{{:{targetLanguageCode}}}")
    shouldTranslateLine = True
    codeBlock = False
    for lineIndex, line in enumerate(inputFileLines):
        if line.startswith("[DO NOT PROCESS LINE]"):
            outputFileDescriptor.write(line[len("[DO NOT PROCESS LINE]"):])

        elif line.strip().endswith(".jpg") or line.strip().endswith(".png"):
            if "|" in line:
                url_path=line.split("|")[0]
                image_path=uploadImage(line.split("|")[1])
                imageLine=f"<a href=\"{url_path}\" target=\"_blank\"><img src=\"{image_path}\"/></a>"
                print(imageLine)
                outputFileDescriptor.write(imageLine)
            else:
                image_path=uploadImage(line)
                image_line=f"<img src=\"{image_path}\"/>"
                print(imageLine)
                outputFileDescriptor.write(image_line)

        elif line.startswith("<") and "frame" in line:
            outputFileDescriptor.write(line)

        elif line.startswith("<a href"):
            outputFileDescriptor.write(line)

        elif line.startswith("</") and "code" in line and "pre" in line:
            shouldTranslateLine = True
            codeBlock = False
            outputFileDescriptor.write("</code></pre></div>")

        elif line.startswith("<") and "pre" in line and "code" in line:
            shouldTranslateLine = False
            codeBlock = True
            codeStateLanguage = line.split("Language: ")[1].strip() if "Language: " in line else "unknown"
            outputFileDescriptor.write(f"<div class=\"hcb_wrap\"><pre class=\"prism undefined-numbers lang-{codeStateLanguage.lower()}\" data-lang=\"{codeStateLanguage}\"><code>")

        elif line.startswith("http://") or line.startswith("https://"):
            outputFileDescriptor.write(processLink(line))

        elif line.startswith("<") and "img " in line:
            outputFileDescriptor.write(line)

        elif line.startswith("<") and "video" in line:
            outputFileDescriptor.write(line)

        elif line.startswith("<") and "source" in line:
            outputFileDescriptor.write(line)

        else:
            if shouldTranslateLine:
                translatedText = translate(line, "google", originalLanguageCode, googleTranslateLanguageCodes[languageIndex])
                outputFileDescriptor.write(translatedText)
            else:
                outputFileDescriptor.write(line)

        if codeBlock == False:
            outputFileDescriptor.write("\n")

    outputFileDescriptor.write("{:}\n")

