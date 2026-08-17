/**
 * Link icon catalogue.
 *
 * A fixed set, mirrored by the backend's `ICON_CATALOGUE`, so a stored icon
 * value is always a known key and is never interpolated into markup.
 *
 * Kept apart from the `LinkIcon` component so that file exports a component and
 * nothing else, which is what keeps fast refresh working.
 */

import {
  Award,
  BookOpen,
  Calendar,
  Camera,
  Code,
  Cpu,
  Download,
  ExternalLink,
  Facebook,
  FileText,
  Github,
  Globe,
  GraduationCap,
  Heart,
  Instagram,
  Link as LinkGlyph,
  Linkedin,
  Mail,
  MapPin,
  Megaphone,
  MessageCircle,
  Phone,
  Presentation,
  Send,
  Slack,
  Star,
  Ticket,
  Twitter,
  Users,
  Youtube,
  Zap,
  type LucideIcon,
} from 'lucide-react';

export const ICON_REGISTRY: Record<string, LucideIcon> = {
  link: LinkGlyph,
  globe: Globe,
  instagram: Instagram,
  linkedin: Linkedin,
  github: Github,
  youtube: Youtube,
  facebook: Facebook,
  twitter: Twitter,
  x: Twitter,
  whatsapp: MessageCircle,
  telegram: Send,
  discord: MessageCircle,
  slack: Slack,
  mail: Mail,
  phone: Phone,
  calendar: Calendar,
  'map-pin': MapPin,
  'file-text': FileText,
  download: Download,
  ticket: Ticket,
  users: Users,
  'book-open': BookOpen,
  'graduation-cap': GraduationCap,
  presentation: Presentation,
  camera: Camera,
  megaphone: Megaphone,
  award: Award,
  code: Code,
  cpu: Cpu,
  zap: Zap,
  star: Star,
  heart: Heart,
  'external-link': ExternalLink,
};

export const FALLBACK_ICON = LinkGlyph;

/** Every icon key the picker offers, in a sensible authoring order. */
export const ICON_KEYS = Object.keys(ICON_REGISTRY);

/** Suggest an icon from the URL so authors rarely have to pick one manually. */
export function guessIcon(url: string): string {
  const value = url.toLowerCase();
  const rules: [string, string][] = [
    ['instagram.com', 'instagram'],
    ['linkedin.com', 'linkedin'],
    ['github.com', 'github'],
    ['youtube.com', 'youtube'],
    ['youtu.be', 'youtube'],
    ['facebook.com', 'facebook'],
    ['twitter.com', 'twitter'],
    ['x.com', 'x'],
    ['wa.me', 'whatsapp'],
    ['whatsapp.com', 'whatsapp'],
    ['t.me', 'telegram'],
    ['telegram', 'telegram'],
    ['discord', 'discord'],
    ['slack.com', 'slack'],
    ['mailto:', 'mail'],
    ['tel:', 'phone'],
    ['forms.gle', 'file-text'],
    ['docs.google.com', 'file-text'],
    ['drive.google.com', 'download'],
    ['eventbrite', 'ticket'],
    ['meetup.com', 'calendar'],
    ['ieee.org', 'cpu'],
  ];
  for (const [needle, icon] of rules) {
    if (value.includes(needle)) return icon;
  }
  return 'globe';
}
