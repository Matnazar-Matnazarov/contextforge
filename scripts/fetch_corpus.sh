#!/usr/bin/env bash
# Downloads a public corpus of real documents for demo/testing into data/corpus/<org-slug>/ (gitignored).
# Sources: IETF RFCs (rfc-editor.org), arXiv papers, Project Gutenberg (public domain), The Rust Book (MIT/Apache-2.0).
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=data/corpus
get() { # dir name url
  local dir="$OUT/$1" name="$2" url="$3"
  mkdir -p "$dir"
  if [ -s "$dir/$name" ]; then echo "skip $dir/$name"; return; fi
  echo "get  $dir/$name"
  curl -fsSL --retry 3 --max-time 120 -A "contextforge-demo-fetch" -o "$dir/$name" "$url" || { echo "FAILED $url"; rm -f "$dir/$name"; }
}

# Org 1: Acme Engineering - internet standards + papers (txt, pdf)
for n in 9110:http-semantics 9112:http1.1 9113:http2 9293:tcp 8446:tls-1.3 7519:jwt 6749:oauth2 6455:websocket 3986:uri 8259:json 5321:smtp 1035:dns; do
  get acme-engineering "rfc${n%%:*}-${n##*:}.txt" "https://www.rfc-editor.org/rfc/rfc${n%%:*}.txt"
done
get acme-engineering rfc9110-http-semantics.pdf "https://www.rfc-editor.org/rfc/rfc9110.pdf"
get acme-engineering attention-is-all-you-need.pdf "https://arxiv.org/pdf/1706.03762"
get acme-engineering bert.pdf "https://arxiv.org/pdf/1810.04805"
get acme-engineering rag-lewis-et-al.pdf "https://arxiv.org/pdf/2005.11401"

# Org 2: Globex Library - public-domain literature (txt)
for n in 1342:pride-and-prejudice 11:alices-adventures 84:frankenstein 1661:sherlock-holmes-adventures 2701:moby-dick 98:tale-of-two-cities 74:tom-sawyer 345:dracula; do
  get globex-library "${n##*:}.txt" "https://www.gutenberg.org/cache/epub/${n%%:*}/pg${n%%:*}.txt"
done

# Org 3: Initech Docs - The Rust Programming Language (markdown)
for c in ch01-00-getting-started ch03-00-common-programming-concepts ch04-00-understanding-ownership ch05-00-using-structs-to-structure-related-data ch06-00-enums ch09-00-error-handling ch10-00-generics ch13-00-functional-features ch15-00-smart-pointers ch16-00-concurrency; do
  get initech-docs "rust-book-$c.md" "https://raw.githubusercontent.com/rust-lang/book/main/src/$c.md"
done
for c in ch04-01-what-is-ownership ch04-02-references-and-borrowing ch09-02-recoverable-errors-with-result ch10-03-lifetime-syntax ch15-01-box ch16-01-threads ch16-03-shared-state; do
  get initech-docs "rust-book-$c.md" "https://raw.githubusercontent.com/rust-lang/book/main/src/$c.md"
done
get initech-docs rust-readme.md "https://raw.githubusercontent.com/rust-lang/rust/master/README.md"
get initech-docs django-readme.md "https://raw.githubusercontent.com/django/django/main/README.rst"
mv -f "$OUT/initech-docs/django-readme.md" "$OUT/initech-docs/django-readme.txt" 2>/dev/null || true

# Org 4: Oʻzbek Bilim Bazasi - Uzbek Wikipedia articles (CC BY-SA 4.0), plain text
wiki() { # file-name title
  local dir="$OUT/uzbek-bilim-bazasi" name="$1.txt" title="$2"
  mkdir -p "$dir"
  if [ -s "$dir/$name" ]; then echo "skip $dir/$name"; return; fi
  echo "get  $dir/$name"
  curl -fsSL --retry 3 --max-time 120 -A "contextforge-demo-fetch/1.0 (local demo)" -G "https://uz.wikipedia.org/w/api.php" \
    --data-urlencode "action=query" --data-urlencode "prop=extracts" --data-urlencode "explaintext=1" \
    --data-urlencode "format=json" --data-urlencode "redirects=1" --data-urlencode "titles=$title" \
    | python3 -c "import json,sys; p=list(json.load(sys.stdin)['query']['pages'].values())[0]; t=p.get('extract',''); sys.exit(1) if len(t)<500 else print('# '+p['title']+'\n\n'+t)" > "$dir/$name" \
    || { echo "FAILED $title"; rm -f "$dir/$name"; }
}
for t in Toshkent Oʻzbekiston Samarqand Buxoro Xiva "Amir Temur" "Alisher Navoiy" "Mirzo Ulugʻbek" "Oʻzbek tili" "Zahiriddin Muhammad Bobur" "Abu Rayhon Beruniy" "Ibn Sino" "Abdulla Qodiriy" "Fargʻona" "Qoraqalpogʻiston" "Oʻzbekiston tarixi" "Navro‘z" "Paxta" "Plov"; do
  wiki "uz-wiki-$(echo "$t" | tr ' ' '-' | tr -cd 'A-Za-z-')" "$t"
done

echo; du -sh "$OUT"/*; find "$OUT" -type f | wc -l
