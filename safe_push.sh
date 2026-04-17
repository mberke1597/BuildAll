#!/bin/bash
# ============================================================
#  BuildAll — Safe GitHub Push
#  API key'leri temizler + force push yapar
# ============================================================

REPO_URL="https://github.com/mberke1597/BuildAll.git"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()     { echo -e "${CYAN}[$(date '+%H:%M:%S')]${RESET} $1"; }
success() { echo -e "${GREEN}✅ $1${RESET}"; }
warn()    { echo -e "${YELLOW}⚠  $1${RESET}"; }
err()     { echo -e "${RED}❌ $1${RESET}"; }

# ============================================================
# 1. .gitignore — hassas dosyaları dışla
# ============================================================
log "📝 .gitignore güncelleniyor..."

ENTRIES=(".env" ".env.local" ".env.production" "*.env" ".venv/" "venv/"
         "__pycache__/" "*.pyc" "node_modules/" ".next/" "*.log" "*.key"
         "*.pem" "secrets.json" ".DS_Store" ".env.example")

for entry in "${ENTRIES[@]}"; do
  grep -qxF "$entry" .gitignore 2>/dev/null || echo "$entry" >> .gitignore
done
success ".gitignore hazır."

# ============================================================
# 2. Hassas dosyaları git index'inden kaldır
# ============================================================
log "🔒 .env ve .venv git takibinden çıkarılıyor..."

for f in .env .env.local .env.production .env.example; do
  git ls-files --error-unmatch "$f" 2>/dev/null && \
    git rm --cached "$f" && warn "$f git'ten kaldırıldı (dosya yerinde kalıyor)."
done

git ls-files --error-unmatch ".venv" 2>/dev/null && \
  git rm -r --cached ".venv/" && warn ".venv/ kaldırıldı."

success "Index temizlendi."

# ============================================================
# 3. Mevcut dosyalarda key tarama
# ============================================================
log "🔍 Commit edilecek dosyalarda API key taraması..."

LIVE_FOUND=false
while IFS= read -r -d '' file; do
  if grep -qE "AIza[0-9A-Za-z_-]{35}|sk-[a-zA-Z0-9]{32,}|ghp_[a-zA-Z0-9]{36}" "$file" 2>/dev/null; then
    err "API key bulundu: $file — commit etme!"
    LIVE_FOUND=true
  fi
done < <(git ls-files -z 2>/dev/null)

if [ "$LIVE_FOUND" = true ]; then
  err "Yukarıdaki dosyalardaki key'leri temizle, sonra tekrar çalıştır."
  exit 1
fi
success "Mevcut dosyalarda key bulunamadı."

# ============================================================
# 4. Git geçmişinde key var mı?
# ============================================================
log "🔍 Git geçmişi taranıyor (bu biraz sürebilir)..."

HISTORY_FOUND=$(git log --all -p 2>/dev/null | \
  grep -E "AIza[0-9A-Za-z_-]{35}|sk-[a-zA-Z0-9]{32,}" | head -1)

if [ -n "$HISTORY_FOUND" ]; then
  warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  warn "Geçmiş commit'lerde API key izleri bulundu!"
  warn "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  echo -e "${BOLD}En güvenli çözüm: Tüm git geçmişini sil, sıfırdan başla${RESET}"
  echo ""
  echo "  1) Geçmişi sıfırla (fresh commit) — ÖNERİLEN"
  echo "  2) Devam et (geçmiş temizlenmeden)"
  echo "  3) İptal"
  read -rp "Seçim (1/2/3): " CHOICE

  case "$CHOICE" in
    1)
      log "Geçmiş sıfırlanıyor — orphan branch yöntemi..."
      git checkout --orphan fresh_main
      git add -A
      git commit -m "feat: BuildAll with ReAct agent layer

- risk_monitor, cost_advisor, document_analyst agents
- ReAct loop: Think → Act → Observe architecture  
- Gemini 2.5 Flash with rate limit handling
- Secure: no API keys committed"
      # Eski branch'i sil
      git branch -D main 2>/dev/null || git branch -D master 2>/dev/null || true
      git branch -m main
      success "Geçmiş temizlendi. Tek commit: clean start."
      ;;
    3)
      log "İptal."; exit 0 ;;
  esac
else
  success "Git geçmişinde API key bulunamadı."
fi

# ============================================================
# 5. COMMIT
# ============================================================
log "📦 Değişiklikler stage ediliyor..."
git add -A

if git diff --cached --quiet; then
  warn "Commit edilecek yeni değişiklik yok, push'a geçiliyor."
else
  git commit -m "chore: remove sensitive files from tracking, update .gitignore"
  success "Commit oluşturuldu."
fi

# ============================================================
# 6. REMOTE & FORCE PUSH
# ============================================================
git remote remove origin 2>/dev/null || true
git remote add origin "$REPO_URL"

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "main")
log "Branch: $CURRENT_BRANCH → $REPO_URL"

echo ""
warn "Force push yapılacak — remote tamamen üzerine yazılacak!"
read -rp "Devam et? (y/n): " CONFIRM
[ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ] && { log "İptal."; exit 0; }

if git push origin "$CURRENT_BRANCH" --force 2>&1; then
  success "Force push başarılı! → $REPO_URL"
else
  echo ""
  warn "GitHub kimlik doğrulama gerekiyor. Şunu dene:"
  echo ""
  echo -e "${BOLD}  Adım 1:${RESET} GitHub'da Personal Access Token oluştur:"
  echo "  https://github.com/settings/tokens/new"
  echo "  (Scope: repo ✓)"
  echo ""
  echo -e "${BOLD}  Adım 2:${RESET} Şu komutla push et:"
  echo "  git push https://mberke1597:TOKEN@github.com/mberke1597/BuildAll.git $CURRENT_BRANCH --force"
fi

echo ""
echo -e "${BOLD}🔐 Önemli: API key'lerini hemen döndür (rotate et):${RESET}"
echo "  Google/Gemini → https://aistudio.google.com/app/apikey"
echo "  GitHub token  → https://github.com/settings/tokens"
echo ""
