import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { PublicLink, Theme } from '@/api/types';

import { PublicPageView } from './PublicPageView';

const theme: Theme = {
  preset: 'ieee-classic',
  primary_color: '#00629B',
  secondary_color: '#0B2545',
  background_color: '#F5F7FA',
  background_end_color: null,
  background_style: 'solid',
  text_color: '#0B1F33',
  button_style: 'solid',
  button_radius: 'lg',
  font: 'inter',
};

const links: PublicLink[] = [
  {
    id: 'link-1',
    title: 'Instagram',
    url: 'https://instagram.com/ieeesou',
    description: 'Weekly updates',
    icon: 'instagram',
    style: { variant: 'default', background_color: null, text_color: null, border_radius: null },
  },
];

describe('PublicPageView', () => {
  it('renders the group name, description and links', () => {
    render(
      <PublicPageView
        name="Computer Society"
        description="IEEE Computer Society chapter"
        organizationName="IEEE SOU"
        theme={theme}
        links={links}
        hrefFor={(link) => `/api/v1/public/groups/computer-society/links/${link.id}`}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Computer Society' })).toBeInTheDocument();
    expect(screen.getByText('IEEE Computer Society chapter')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Instagram/ })).toBeInTheDocument();
  });

  it('routes clicks through the tracking redirect, not the raw URL', () => {
    render(
      <PublicPageView
        name="Computer Society"
        theme={theme}
        links={links}
        hrefFor={(link) => `/api/v1/public/groups/computer-society/links/${link.id}`}
      />,
    );

    const anchor = screen.getByRole('link', { name: /Instagram/ });
    expect(anchor).toHaveAttribute(
      'href',
      '/api/v1/public/groups/computer-society/links/link-1',
    );
  });

  it('opens outbound links without leaking the opener or referrer', () => {
    render(
      <PublicPageView
        name="Computer Society"
        theme={theme}
        links={links}
        hrefFor={() => 'https://example.org'}
      />,
    );

    const rel = screen.getByRole('link', { name: /Instagram/ }).getAttribute('rel') ?? '';
    expect(rel).toContain('noopener');
    expect(rel).toContain('noreferrer');
  });

  it('escapes markup in user-supplied text rather than rendering it', () => {
    const { container } = render(
      <PublicPageView
        name="<img src=x onerror=alert(1)>Robotics"
        description="<script>alert('xss')</script>"
        theme={theme}
        links={[]}
      />,
    );

    // The payload is present as text, and no element was created from it.
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('img[onerror]')).toBeNull();
    expect(screen.getByRole('heading')).toHaveTextContent('Robotics');
  });

  it('shows an empty state when there are no links', () => {
    render(<PublicPageView name="Empty Group" theme={theme} links={[]} />);
    expect(screen.getByText('No links yet.')).toBeInTheDocument();
  });

  it('renders links as non-interactive in preview mode', () => {
    render(<PublicPageView name="Preview" theme={theme} links={links} isPreview />);
    expect(screen.queryByRole('link')).toBeNull();
    expect(screen.getByText('Instagram')).toBeInTheDocument();
  });
});
