# Testing the Personal OS Mobile App via Expo Go

This guide is for external iPhone testers joining via Expo Go.

---

## For Testers

### Step 1 — Install Expo Go
Download **Expo Go** from the App Store:
https://apps.apple.com/app/expo-go/id982107779

### Step 2 — Get Your Token
Open Telegram and message the Personal OS bot:
```
/token
```
The bot replies with a one-time auth token. Copy it.

### Step 3 — Open the App
The developer will share either:
- A **QR code** — scan it from the Camera app or directly inside Expo Go
- An **exp://** link — tap it to open directly in Expo Go

### Step 4 — Sign In
On the Auth screen, paste your token into the Token field and tap **Sign In**.

---

## For Developers

### Start with Tunnel (recommended for external testers)
```bash
npm run start:tunnel
```
This uses ngrok to expose the app over the internet. Share the QR code or `exp://` link that appears in the terminal.

> Requires `@expo/ngrok` to be installed globally or in the project.
> If missing: `npm install -g @expo/ngrok@^4.1.0`

### Start on LAN (same Wi-Fi network)
```bash
npm run start:lan
```
Works for testers on the same network. Faster than tunnel.

### Start on Localhost (local device only)
```bash
npm run start:localhost
```

### Share the Link
After starting, Expo CLI prints:
- A **QR code** — screenshot it and share it
- An **exp://** URL — copy it from the terminal and paste it to the tester

---

## Troubleshooting

| Issue | Fix |
|---|---|
| "Network response timed out" in Expo Go | Use `start:tunnel` instead of LAN |
| QR code opens Safari instead of Expo Go | Make sure Expo Go is installed, then scan from inside the Expo Go app |
| Token rejected / "Invalid token" | Request a fresh token with `/token` in Telegram — tokens expire |
| App loads but shows blank screen | Force-close Expo Go and reopen the link |
| Tunnel fails to start | Run `npx expo start --tunnel` directly; install `@expo/ngrok` if prompted |
| "Something went wrong" on sign-in | Check the backend is running and the API URL in the app matches the server |

---

## Backend URL

The app connects to the Personal OS API. On first launch you can configure the backend URL in **Settings > Tester Info**. Default: `http://95.111.252.176:3000`.
