# Personal OS — Mobile App

React Native (Expo) app for the Personal OS project.

## Prerequisites

- Node.js 18+
- [Expo CLI](https://docs.expo.dev/get-started/installation/): `npm install -g expo-cli`
- For iOS: macOS + Xcode + iOS Simulator
- For Android: Android Studio + emulator (or physical device with Expo Go)

## Setup

```bash
cd mobile-app
npm install
```

## Running

```bash
# Start Metro bundler (scan QR with Expo Go on device)
npm start

# iOS Simulator
npm run ios

# Android Emulator
npm run android
```

## Project Structure

```
mobile-app/
  App.tsx                  # Root component, navigation container
  src/
    navigation/
      TabNavigator.tsx     # Bottom tab navigator (6 tabs)
    screens/
      HomeScreen.tsx       # Dashboard / daily overview
      TasksScreen.tsx      # Task management
      CalendarScreen.tsx   # Calendar view
      RoutinesScreen.tsx   # Daily routines
      FitnessScreen.tsx    # Fitness tracking
      SettingsScreen.tsx   # App settings
    components/            # Shared UI components
```

## Tabs

| Tab | Screen | Description |
|-----|--------|-------------|
| Home | HomeScreen | Daily command center |
| Tasks | TasksScreen | Task list & objectives |
| Calendar | CalendarScreen | Scheduled events |
| Routines | RoutinesScreen | Daily routine tracker |
| Fitness | FitnessScreen | Workouts & splits |
| Settings | SettingsScreen | Config & preferences |
