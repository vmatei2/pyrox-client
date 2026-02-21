# Branding Customization Notes

Use these files as the single source of truth for splash/loading branding.

## 1) Wordmark Asset
- File: `ui/public/brand-wordmark.svg`
- Used by:
  - first-paint web splash in `ui/index.html`
  - in-app loading screen component `ui/src/components/AppLoadingScreen.jsx`

## 2) Native iOS Launch Screen
- File: `ui/ios/App/App/Base.lproj/LaunchScreen.storyboard`
- Update:
  - background color
  - `PYROX` wordmark text

## 3) Loading Screen Visuals
- File: `ui/src/style_layers/bootstrap.css`
- Update:
  - `.bootstrap-screen` background
  - `.bootstrap-wordmark` size/shadow
  - `.bootstrap-progress-bar` accent color

## 4) Shared Premium Theme
- Files:
  - `ui/src/style_layers/premium_tokens.css`
  - `ui/src/style_layers/premium_primitives.css`
  - `ui/src/style_layers/premium_flow.css`
- Update global tokens first (`premium_tokens.css`) before per-component rules.
