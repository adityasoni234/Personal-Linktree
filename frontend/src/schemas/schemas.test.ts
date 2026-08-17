import { describe, expect, it } from 'vitest';

import {
  emailSchema,
  linkUrlSchema,
  loginFormSchema,
  passwordSchema,
  passwordStrength,
  registerFormSchema,
  slugSchema,
} from './index';

describe('linkUrlSchema', () => {
  it.each([
    'javascript:alert(1)',
    'JavaScript:alert(document.cookie)',
    '  javascript:alert(1)',
    'data:text/html;base64,PHNjcmlwdD4=',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    'blob:https://example.com/x',
  ])('rejects the dangerous scheme %s', (payload) => {
    expect(linkUrlSchema.safeParse(payload).success).toBe(false);
  });

  it('normalises a bare domain to https', () => {
    const result = linkUrlSchema.safeParse('ieeesou.org/events');
    expect(result.success).toBe(true);
    if (result.success) expect(result.data).toBe('https://ieeesou.org/events');
  });

  it.each([
    'https://instagram.com/ieeesou',
    'http://ieeesou.org',
    'mailto:chair@ieeesou.org',
    'tel:+919900000000',
  ])('accepts %s', (payload) => {
    expect(linkUrlSchema.safeParse(payload).success).toBe(true);
  });

  it('rejects a host without a dot', () => {
    expect(linkUrlSchema.safeParse('https://localhost').success).toBe(false);
  });

  it('rejects an over-long URL', () => {
    expect(linkUrlSchema.safeParse(`https://example.com/${'a'.repeat(3000)}`).success).toBe(
      false,
    );
  });
});

describe('slugSchema', () => {
  it.each(['admin', 'api', 'login', 'dashboard', 'settings', 'g'])(
    'rejects the reserved slug %s',
    (slug) => {
      expect(slugSchema.safeParse(slug).success).toBe(false);
    },
  );

  it.each(['../etc', 'has space', '-lead', 'trail-', 'ab', '12345', 'double--hyphen'])(
    'rejects the malformed slug %s',
    (slug) => {
      expect(slugSchema.safeParse(slug).success).toBe(false);
    },
  );

  it('accepts and lowercases a valid slug', () => {
    // Matches the server, which also normalises before validating.
    const result = slugSchema.safeParse('Computer-Society');
    expect(result.success).toBe(true);
    if (result.success) expect(result.data).toBe('computer-society');
  });
});

describe('emailSchema', () => {
  it('lowercases and trims', () => {
    const result = emailSchema.safeParse('  Chair@IEEESOU.org ');
    expect(result.success).toBe(true);
    if (result.success) expect(result.data).toBe('chair@ieeesou.org');
  });

  it('rejects an invalid address', () => {
    expect(emailSchema.safeParse('not-an-email').success).toBe(false);
  });
});

describe('passwordSchema', () => {
  it.each(['short1!A', 'alllowercase123', 'aaaaAAAA1111', 'password123'])(
    'rejects the weak password %s',
    (password) => {
      expect(passwordSchema.safeParse(password).success).toBe(false);
    },
  );

  it('accepts a strong password', () => {
    expect(passwordSchema.safeParse('Str0ng-Test-Pass!42').success).toBe(true);
  });
});

describe('loginFormSchema', () => {
  it('does not apply the strength policy to an existing password', () => {
    // Re-validating an old password here would lock people out of their own
    // sign-in form after a policy change.
    const result = loginFormSchema.safeParse({
      email: 'chair@ieeesou.org',
      password: 'old-weak',
      remember_me: false,
    });
    expect(result.success).toBe(true);
  });
});

describe('registerFormSchema', () => {
  const valid = {
    full_name: 'Aarav Shah',
    email: 'aarav@ieeesou.org',
    password: 'Str0ng-Test-Pass!42',
    confirm_password: 'Str0ng-Test-Pass!42',
    accept_terms: true as const,
  };

  it('accepts a complete valid form', () => {
    expect(registerFormSchema.safeParse(valid).success).toBe(true);
  });

  it('rejects mismatched passwords', () => {
    const result = registerFormSchema.safeParse({ ...valid, confirm_password: 'Different!42x' });
    expect(result.success).toBe(false);
  });

  it('rejects a password containing the email local part', () => {
    const result = registerFormSchema.safeParse({
      ...valid,
      password: 'Aarav-Str0ng!42',
      confirm_password: 'Aarav-Str0ng!42',
    });
    expect(result.success).toBe(false);
  });

  it('requires the terms checkbox', () => {
    const result = registerFormSchema.safeParse({ ...valid, accept_terms: false });
    expect(result.success).toBe(false);
  });
});

describe('passwordStrength', () => {
  it('scores an empty password as zero', () => {
    expect(passwordStrength('').score).toBe(0);
  });

  it('rates a long mixed password highly', () => {
    expect(passwordStrength('Str0ng-Test-Pass!42').score).toBeGreaterThanOrEqual(3);
  });

  it('penalises repeated characters', () => {
    expect(passwordStrength('Aaaaa1111!!!!').score).toBeLessThan(
      passwordStrength('Str0ng-Test-Pass!42').score,
    );
  });
});
