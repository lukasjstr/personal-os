import { Ionicons } from '@expo/vector-icons';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import CalendarScreen from '../screens/CalendarScreen';
import FitnessScreen from '../screens/FitnessScreen';
import HomeScreen from '../screens/HomeScreen';
import RoutinesScreen from '../screens/RoutinesScreen';
import SettingsScreen from '../screens/SettingsScreen';
import ShoppingScreen from '../screens/ShoppingScreen';
import TasksScreen from '../screens/TasksScreen';

export type TabParamList = {
  Home: undefined;
  Tasks: undefined;
  Calendar: undefined;
  Routines: undefined;
  Fitness: undefined;
  Shopping: undefined;
  Settings: undefined;
};

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

const TAB_ICONS: Record<keyof TabParamList, { focused: IoniconName; default: IoniconName }> = {
  Home: { focused: 'home', default: 'home-outline' },
  Tasks: { focused: 'checkmark-circle', default: 'checkmark-circle-outline' },
  Calendar: { focused: 'calendar', default: 'calendar-outline' },
  Routines: { focused: 'repeat', default: 'repeat-outline' },
  Fitness: { focused: 'fitness', default: 'fitness-outline' },
  Shopping: { focused: 'cart', default: 'cart-outline' },
  Settings: { focused: 'settings', default: 'settings-outline' },
};

const Tab = createBottomTabNavigator<TabParamList>();

const COLORS = {
  active: '#6366f1',
  inactive: '#9ca3af',
  background: '#111827',
  border: '#1f2937',
};

export default function TabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          const icons = TAB_ICONS[route.name as keyof TabParamList];
          const name = focused ? icons.focused : icons.default;
          return <Ionicons name={name} size={size} color={color} />;
        },
        tabBarActiveTintColor: COLORS.active,
        tabBarInactiveTintColor: COLORS.inactive,
        tabBarStyle: {
          backgroundColor: COLORS.background,
          borderTopColor: COLORS.border,
          borderTopWidth: 1,
        },
        headerStyle: {
          backgroundColor: COLORS.background,
          borderBottomColor: COLORS.border,
          borderBottomWidth: 1,
        },
        headerTintColor: '#f9fafb',
        headerTitleStyle: {
          fontWeight: '600',
        },
      })}
    >
      <Tab.Screen name="Home" component={HomeScreen} />
      <Tab.Screen name="Tasks" component={TasksScreen} />
      <Tab.Screen name="Calendar" component={CalendarScreen} />
      <Tab.Screen name="Routines" component={RoutinesScreen} />
      <Tab.Screen name="Fitness" component={FitnessScreen} />
      <Tab.Screen name="Shopping" component={ShoppingScreen} />
      <Tab.Screen name="Settings" component={SettingsScreen} />
    </Tab.Navigator>
  );
}
