import { useRouter } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/ui/app-text';
import { Button } from '@/components/ui/button';
import { Screen } from '@/components/ui/screen';
import { spacing } from '@/theme';

export default function NotFoundScreen() {
  const router = useRouter();
  return (
    <Screen>
      <View style={styles.wrap}>
        <AppText variant="display">404</AppText>
        <AppText variant="h2">This screen does not exist</AppText>
        <AppText variant="body" color="textSecondary" style={styles.message}>
          The link may be outdated. Head back to the tender feed to keep browsing public
          procurement notices.
        </AppText>
        <Button label="Back to home" icon="home-outline" onPress={() => router.replace('/')} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
    gap: spacing.md,
  },
  message: {
    textAlign: 'center',
    maxWidth: 320,
    marginBottom: spacing.md,
  },
});
