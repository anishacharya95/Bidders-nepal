import { Tabs } from 'expo-router';

import { TabBar } from '@/components/layout/tab-bar';

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{ headerShown: false, lazy: true }}
      tabBar={(props) => <TabBar {...props} />}>
      <Tabs.Screen name="index" options={{ title: 'Home' }} />
      <Tabs.Screen name="explore" options={{ title: 'Explore' }} />
      <Tabs.Screen name="saved" options={{ title: 'Saved' }} />
      <Tabs.Screen name="documents" options={{ title: 'Documents' }} />
      <Tabs.Screen name="notifications" options={{ title: 'Notifications' }} />
      <Tabs.Screen name="profile" options={{ title: 'Profile' }} />
    </Tabs>
  );
}
