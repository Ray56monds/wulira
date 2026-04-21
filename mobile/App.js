import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { StatusBar } from 'expo-status-bar';
import { Text } from 'react-native';
import HomeScreen from './src/screens/HomeScreen';
import JobsScreen from './src/screens/JobsScreen';
import LyricsScreen from './src/screens/LyricsScreen';

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <StatusBar style="light" />
      <Tab.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: '#0a0a0f' },
          headerTintColor: '#a29bfe',
          tabBarStyle: { backgroundColor: '#12121a', borderTopColor: '#2a2a3a' },
          tabBarActiveTintColor: '#a29bfe',
          tabBarInactiveTintColor: '#888',
        }}
      >
        <Tab.Screen
          name="Extract"
          component={HomeScreen}
          options={{ tabBarIcon: () => <Text style={{ fontSize: 20 }}>🎤</Text>, title: 'Wulira' }}
        />
        <Tab.Screen
          name="Jobs"
          component={JobsScreen}
          options={{ tabBarIcon: () => <Text style={{ fontSize: 20 }}>📋</Text> }}
        />
        <Tab.Screen
          name="Lyrics"
          component={LyricsScreen}
          options={{ tabBarIcon: () => <Text style={{ fontSize: 20 }}>🎵</Text> }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
