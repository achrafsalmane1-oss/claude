import { useEffect } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import { loadSession } from '../store/auth';
import { Colors, Typography, Spacing } from '../constants/theme';

export default function SplashScreen() {
  useEffect(() => {
    async function boot() {
      await new Promise(r => setTimeout(r, 1800));
      const session = await loadSession();
      if (session?.token) {
        router.replace('/home');
      } else {
        router.replace('/onboarding');
      }
    }
    boot();
  }, []);

  return (
    <LinearGradient
      colors={['#080808', '#0d1a15', '#080808']}
      style={styles.container}
    >
      <View style={styles.logo}>
        {/* Haven logo mark — circle with inner dune/arc */}
        <View style={styles.logoOuter}>
          <View style={styles.logoInner} />
        </View>
      </View>
      <Text style={styles.name}>Haven</Text>
      <Text style={styles.tagline}>Halal savings. Real returns.</Text>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.background,
  },
  logo: {
    marginBottom: Spacing.lg,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoOuter: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: 2.5,
    borderColor: Colors.accent,
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoInner: {
    width: 36,
    height: 18,
    borderRadius: 18,
    borderWidth: 2,
    borderColor: Colors.accent,
    borderBottomWidth: 0,
  },
  name: {
    ...Typography.h1,
    letterSpacing: 2,
    marginBottom: Spacing.sm,
  },
  tagline: {
    ...Typography.small,
    color: Colors.textSecondary,
    letterSpacing: 0.5,
  },
});
