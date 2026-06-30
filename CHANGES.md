# SmartQuiz v5 — Improvements

## 🔒 Security Fixes
- Secret key now loaded from env variable (not hardcoded)
- Gmail password now loaded from env variable (not hardcoded)
- Added `.env.example` template for safe configuration
- Students can only view their OWN results (access control fix)
- Uploaded file paths sanitized with secure_filename
- Redirect if already logged in (prevent double login)
- Input validation on all POST forms

## ✨ New Features
- **Question Navigator**: Sidebar panel during quiz to jump to any question + see answered/unanswered status
- **Confirm Submit Modal**: Shows how many questions answered before final submission
- **Answer Review**: Result page now shows all questions with correct/wrong/skipped answers highlighted
- **Animated Score**: Score circle animates from 0 to final percentage on result page
- **Student Profile Page**: Edit name, roll number, and change password
- **Best Score stat** added to dashboard (alongside avg)
- **Delete Result**: Admin can delete individual results
- **Error pages**: Custom 404 and 500 error pages
- **Scroll-to-top button**: Appears on long pages

## 🎨 UI/UX Improvements
- **Mobile navbar**: Hamburger toggle menu on small screens
- Quiz timer warning now triggers at 60s (was 30s)
- Progress bar in sticky header (quiz page)
- Auto-save indicator (visual feedback)
- Confirm password field on registration
- Navbar includes Profile link
- Better flash message for "email not found" (security)

## ⚙️ Code Quality
- Proper `@wraps` decorator on auth decorators
- `student_required` and `admin_required` decorators used consistently
- Removed duplicate `data-result-id` attribute in quiz form
- `debug=False` in production run
- Cleaner `get_answers()` with proper validation
- Better error handling in submit flow
