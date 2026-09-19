# 🧪 Testing Guide - Editorrah Landing Page

## 🚀 Quick Start

### 1. Start Dev Server (if not running)
```bash
cd /Users/rahulkumargupta/Desktop/working_integrityv2/umo
npm run dev
```

### 2. Open Landing Page
Browser will auto-open or manually visit:
- **Landing Page**: http://localhost:9000/landing.html
- **Auto-redirect**: http://localhost:9000/ (redirects to landing)
- **Direct Editor**: http://localhost:9000/editor/1

---

## ✅ Testing Checklist

### Landing Page Tests

#### Visual Design
- [ ] Hero section displays with purple gradient
- [ ] "Editorrah" logo visible in navbar
- [ ] Trust indicators show (98%, 500+, 1M+, 24/7)
- [ ] All 9 feature cards display correctly
- [ ] Footer displays with all links

#### Functionality
- [ ] "Launch Editor Now" button works (redirects to `/editor/1`)
- [ ] Smooth scroll navigation works
- [ ] Navbar becomes sticky on scroll
- [ ] All section links work (#features, #how-it-works, etc.)
- [ ] Footer links clickable

#### Responsive Design
- [ ] Test on desktop (full width)
- [ ] Test on tablet (768px)
- [ ] Test on mobile (375px)
- [ ] All text readable on all sizes
- [ ] Buttons work on mobile

#### Performance
- [ ] Page loads quickly (< 2 seconds)
- [ ] No console errors
- [ ] Animations smooth
- [ ] Images load (if any)

### Editor Integration Tests

#### Navigation
- [ ] Landing page → Editor works
- [ ] Editor → Back to landing works
- [ ] Direct URL `/editor/1` works

#### Integrity System
- [ ] Editor loads with integrity tracking
- [ ] Paste detection works
- [ ] "Analyze Integrity" button works
- [ ] PDF export includes integrity report
- [ ] Trust score calculates correctly

### SEO Tests

#### Meta Tags
- [ ] Check page source for meta description
- [ ] Check page source for Open Graph tags
- [ ] Check page source for Schema.org markup

#### Files
- [ ] http://localhost:9000/robots.txt loads
- [ ] http://localhost:9000/sitemap.xml loads

---

## 🔍 Detailed Testing Steps

### Test 1: Landing Page Load
```
1. Open: http://localhost:9000/landing.html
2. Wait for page to fully load
3. Check: Purple gradient hero section visible
4. Check: "Academic Integrity Platform" headline visible
5. Check: "Launch Editor Now" button visible
```

### Test 2: CTA Buttons
```
1. Click "Launch Editor Now" in hero section
2. Should redirect to: http://localhost:9000/editor/1
3. Verify editor loads
4. Click browser back button
5. Should return to landing page
```

### Test 3: Navigation
```
1. Click "Features" in navbar
2. Should smooth scroll to features section
3. Click "How It Works"
4. Should smooth scroll to how-it-works section
5. Click "For Universities"
6. Should smooth scroll to universities section
```

### Test 4: Responsive Design
```
1. Open browser DevTools (F12)
2. Click device toolbar (Cmd+Shift+M / Ctrl+Shift+M)
3. Test these sizes:
   - iPhone SE (375px)
   - iPad (768px)
   - Desktop (1200px)
4. Check: All content visible and readable
```

### Test 5: Editor Integration
```
1. From landing page, click "Launch Editor Now"
2. In editor:
   - Type some text
   - Copy and paste from external source
   - Click "Analyze Integrity Now"
   - Check trust score appears
   - Export to PDF
   - Verify integrity report in PDF
```

### Test 6: SEO Check
```
1. Right-click page → "View Page Source"
2. Search for (Cmd/Ctrl + F):
   - "Editorrah - Academic Integrity Platform"
   - "og:title"
   - "schema.org"
3. All should be present
```

---

## 🐛 Common Issues & Fixes

### Issue: Dev server not starting
**Fix:**
```bash
# Kill existing process
lsof -i:9000 | grep LISTEN | awk '{print $2}' | xargs kill -9

# Restart
npm run dev
```

### Issue: Landing page shows 404
**Fix:**
```bash
# Verify file exists
ls -la public/landing.html

# If missing, copy it
cp landing.html public/
```

### Issue: "Launch Editor" button doesn't work
**Check:**
1. Console for errors (F12)
2. URL should change to `/editor/1`
3. If not, check router.js configuration

### Issue: Styles look broken
**Fix:**
- Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
- Clear cache and reload

### Issue: MongoDB not connected
**Fix:**
```bash
cd integrity-backend
python test_mongodb.py
# Should show: ✅ Connection successful!
```

---

## 📊 Browser Testing

### Test in Multiple Browsers
- [ ] Chrome/Edge (Chromium)
- [ ] Firefox
- [ ] Safari (Mac only)
- [ ] Mobile Safari (iPhone)
- [ ] Mobile Chrome (Android)

---

## 🎯 Key Things to Verify

### Landing Page
1. **Hero CTA**: Big "Launch Editor Now" button works
2. **Features**: All 9 feature cards visible
3. **Trust Indicators**: Stats showing (98%, 500+, etc.)
4. **Responsive**: Works on mobile
5. **Fast**: Loads in < 2 seconds

### Editor Integration
1. **Navigation**: Landing → Editor works
2. **Integrity**: Paste detection works
3. **Reports**: PDF export includes integrity report
4. **Database**: MongoDB connected (check backend logs)

### Production Readiness
1. **SEO**: Meta tags present
2. **Performance**: Fast loading
3. **Mobile**: Fully responsive
4. **Links**: All buttons/links work

---

## 🚀 Quick Test Command

Run this to verify everything:
```bash
# 1. Check dev server
lsof -i:9000 | grep LISTEN

# 2. Test landing page
curl -s http://localhost:9000/landing.html | grep "Academic Integrity Platform"

# 3. Test robots.txt
curl -s http://localhost:9000/robots.txt | grep "Sitemap"

# 4. Test sitemap
curl -s http://localhost:9000/sitemap.xml | grep "editorrah.com"

# All should return results ✅
```

---

## 📝 Testing Notes

**What to look for:**
- Clean, professional design
- Purple gradient (Turnitin-style)
- All buttons clickable
- Smooth animations
- No console errors
- Fast page load

**What to report:**
- Any broken links
- Any visual glitches
- Any console errors
- Any slow loading
- Any mobile issues

---

## ✅ Success Criteria

Landing page is ready when:
- [ ] All CTAs work
- [ ] Navigation smooth
- [ ] Mobile responsive
- [ ] No console errors
- [ ] Editor integration works
- [ ] SEO tags present
- [ ] Fast loading (< 2s)
- [ ] Professional appearance

---

**Ready to test!** 🎉

Visit: **http://localhost:9000/landing.html**

