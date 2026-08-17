import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  ChevronDown,
  ChevronUp,
  Copy,
  EyeOff,
  GripVertical,
  Link2,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react';

import { linksApi } from '@/api/endpoints';
import type { LinkItem } from '@/api/types';
import { LinkIcon } from '@/components/public/LinkIcon';
import { ICON_KEYS, guessIcon } from '@/lib/icons';
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ConfirmDialog,
  EmptyState,
  IconButton,
  Input,
  Menu,
  Modal,
  Select,
  Switch,
  Textarea,
} from '@/components/ui';
import { useReorder } from '@/hooks';
import { cn, formatNumber, prettyUrl } from '@/lib/utils';
import { linkFormSchema, type LinkFormValues } from '@/schemas';
import { toast } from '@/stores/toast';

interface LinksPanelProps {
  groupId: string | null;
  links: LinkItem[];
  onChange: (links: LinkItem[]) => void;
}

const ICON_OPTIONS = ICON_KEYS.map((key) => ({
  value: key,
  label: key.replace(/-/g, ' ').replace(/^\w/, (character) => character.toUpperCase()),
}));

function LinkDialog({
  open,
  onClose,
  onSubmit,
  initial,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (values: LinkFormValues) => Promise<void>;
  initial: LinkItem | null;
}) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<LinkFormValues>({
    resolver: zodResolver(linkFormSchema),
    values: {
      title: initial?.title ?? '',
      url: initial?.url ?? '',
      description: initial?.description ?? '',
      icon: initial?.icon ?? 'globe',
      is_active: initial?.is_active ?? true,
    },
  });

  const url = watch('url');
  const icon = watch('icon');
  const isActive = watch('is_active');

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initial ? 'Edit link' : 'Add a link'}
      description="Only http:// and https:// links are accepted (plus mailto: and tel:)."
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button
            isLoading={isSubmitting}
            onClick={handleSubmit(async (values) => {
              await onSubmit(values);
              reset();
            })}
          >
            {initial ? 'Save changes' : 'Add link'}
          </Button>
        </>
      }
    >
      <form
        className="space-y-4"
        onSubmit={handleSubmit(async (values) => {
          await onSubmit(values);
          reset();
        })}
        noValidate
      >
        <Input
          label="Title"
          required
          autoFocus
          placeholder="Instagram"
          error={errors.title?.message}
          {...register('title')}
        />

        <Input
          label="URL"
          required
          placeholder="instagram.com/ieeesou"
          error={errors.url?.message}
          hint="A bare domain is fine — we will add https:// for you."
          {...register('url')}
          onBlur={(event) => {
            // Suggest an icon once there is something to go on.
            if (event.target.value && (!icon || icon === 'globe')) {
              setValue('icon', guessIcon(event.target.value));
            }
          }}
        />

        <Textarea
          label="Description"
          placeholder="Optional — shown under the title"
          rows={2}
          error={errors.description?.message}
          {...register('description')}
        />

        <div className="flex items-end gap-3">
          <Select
            label="Icon"
            options={ICON_OPTIONS}
            className="flex-1"
            {...register('icon')}
          />
          <span className="mb-0.5 flex h-11 w-11 items-center justify-center rounded-xl bg-ieee-50 text-ieee-600">
            <LinkIcon name={icon} />
          </span>
        </div>

        <Switch
          label="Visible on the public page"
          description={
            isActive
              ? 'This link is shown to visitors.'
              : 'Hidden — you can turn it back on any time.'
          }
          checked={isActive}
          onChange={(value) => setValue('is_active', value)}
        />

        {url && (
          <div className="rounded-xl border border-navy-200 bg-surface-subtle p-3">
            <p className="text-2xs uppercase tracking-wide text-navy-400">Destination</p>
            <p className="mt-1 break-all font-mono text-xs text-navy-700">{url}</p>
          </div>
        )}
      </form>
    </Modal>
  );
}

export function LinksPanel({ groupId, links, onChange }: LinksPanelProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<LinkItem | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<LinkItem | null>(null);
  const [isPending, setIsPending] = useState(false);

  const persistOrder = async (ordered: LinkItem[]) => {
    onChange(ordered.map((link, index) => ({ ...link, position: index })));
    if (!groupId) return;
    try {
      await linksApi.reorder(
        groupId,
        ordered.map((link, index) => ({ id: link.id, position: index })),
      );
    } catch {
      toast.error('Could not save the new order');
    }
  };

  const { draggingId, overId, handlers, moveItem } = useReorder(links, (ordered) => {
    void persistOrder(ordered);
  });

  const handleSubmit = async (values: LinkFormValues) => {
    if (!groupId) {
      toast.info('Save the group first', 'Links can be added once the group exists.');
      return;
    }
    try {
      if (editing) {
        const updated = await linksApi.update(editing.id, values);
        onChange(links.map((link) => (link.id === updated.id ? updated : link)));
        toast.success('Link updated');
      } else {
        const created = await linksApi.create(groupId, values);
        onChange([...links, created]);
        toast.success('Link added');
      }
      setDialogOpen(false);
      setEditing(null);
    } catch (error) {
      toast.error(
        'Could not save the link',
        error instanceof Error ? error.message : undefined,
      );
    }
  };

  const toggleActive = async (link: LinkItem) => {
    try {
      const updated = await linksApi.update(link.id, { is_active: !link.is_active });
      onChange(links.map((item) => (item.id === updated.id ? updated : item)));
    } catch {
      toast.error('Could not update the link');
    }
  };

  return (
    <>
      <Card>
        <CardHeader
          title="Links"
          description={`${links.length} link${links.length === 1 ? '' : 's'} · drag to reorder`}
          icon={<Link2 className="h-4 w-4" aria-hidden="true" />}
          action={
            <Button
              size="sm"
              leftIcon={<Plus className="h-4 w-4" />}
              onClick={() => {
                setEditing(null);
                setDialogOpen(true);
              }}
            >
              Add link
            </Button>
          }
        />
        <CardBody className={links.length === 0 ? 'p-5' : 'p-3'}>
          {links.length === 0 ? (
            <EmptyState
              className="border-0 bg-transparent py-8"
              icon={<Link2 className="h-6 w-6" aria-hidden="true" />}
              title="No links yet"
              description="Add your social profiles, registration forms and websites. They appear on the public page in this order."
              action={
                <Button
                  leftIcon={<Plus className="h-4 w-4" />}
                  onClick={() => {
                    setEditing(null);
                    setDialogOpen(true);
                  }}
                >
                  Add your first link
                </Button>
              }
            />
          ) : (
            <ul className="space-y-2">
              {links.map((link, index) => (
                <li
                  key={link.id}
                  {...handlers(link.id)}
                  className={cn(
                    'group flex items-center gap-3 rounded-xl border bg-white p-3 transition',
                    draggingId === link.id
                      ? 'opacity-40'
                      : overId === link.id
                        ? 'border-ieee-400 ring-2 ring-ieee-600/20'
                        : 'border-navy-200/70 hover:border-navy-300',
                    !link.is_active && 'bg-surface-subtle',
                  )}
                >
                  <span
                    className="cursor-grab text-navy-300 transition group-hover:text-navy-500 active:cursor-grabbing"
                    aria-hidden="true"
                  >
                    <GripVertical className="h-4 w-4" />
                  </span>

                  <span
                    className={cn(
                      'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                      link.is_active
                        ? 'bg-ieee-50 text-ieee-600'
                        : 'bg-navy-100 text-navy-400',
                    )}
                  >
                    <LinkIcon name={link.icon} className="h-4 w-4" />
                  </span>

                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 truncate text-sm font-medium text-navy-900">
                      {link.title}
                      {!link.is_active && (
                        <Badge tone="neutral" size="sm">
                          <EyeOff className="h-3 w-3" aria-hidden="true" />
                          Hidden
                        </Badge>
                      )}
                    </p>
                    <p className="truncate font-mono text-2xs text-navy-400">
                      {prettyUrl(link.url)}
                    </p>
                  </div>

                  {link.click_count > 0 && (
                    <span className="hidden shrink-0 text-2xs text-navy-400 sm:block">
                      {formatNumber(link.click_count)} clicks
                    </span>
                  )}

                  {/* Keyboard-accessible reordering — dragging alone would
                      exclude keyboard and screen-reader users. */}
                  <span className="flex shrink-0 flex-col">
                    <IconButton
                      size="sm"
                      label={`Move ${link.title} up`}
                      icon={<ChevronUp className="h-3.5 w-3.5" />}
                      disabled={index === 0}
                      onClick={() => moveItem(link.id, -1)}
                      className="h-5 w-7"
                    />
                    <IconButton
                      size="sm"
                      label={`Move ${link.title} down`}
                      icon={<ChevronDown className="h-3.5 w-3.5" />}
                      disabled={index === links.length - 1}
                      onClick={() => moveItem(link.id, 1)}
                      className="h-5 w-7"
                    />
                  </span>

                  <Menu
                    label={`Actions for ${link.title}`}
                    items={[
                      {
                        label: 'Edit',
                        icon: <Pencil className="h-4 w-4" />,
                        onSelect: () => {
                          setEditing(link);
                          setDialogOpen(true);
                        },
                      },
                      {
                        label: link.is_active ? 'Hide from page' : 'Show on page',
                        icon: <EyeOff className="h-4 w-4" />,
                        onSelect: () => void toggleActive(link),
                      },
                      {
                        label: 'Duplicate',
                        icon: <Copy className="h-4 w-4" />,
                        onSelect: () => {
                          void linksApi
                            .duplicate(link.id)
                            .then((copy) => {
                              onChange([...links, copy]);
                              toast.success('Link duplicated', 'The copy starts hidden.');
                            })
                            .catch(() => toast.error('Could not duplicate the link'));
                        },
                      },
                      {
                        label: 'Delete',
                        icon: <Trash2 className="h-4 w-4" />,
                        tone: 'danger',
                        separated: true,
                        onSelect: () => setConfirmDelete(link),
                      },
                    ]}
                  />
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <LinkDialog
        open={dialogOpen}
        onClose={() => {
          setDialogOpen(false);
          setEditing(null);
        }}
        onSubmit={handleSubmit}
        initial={editing}
      />

      <ConfirmDialog
        open={confirmDelete !== null}
        onClose={() => setConfirmDelete(null)}
        isPending={isPending}
        title="Delete this link?"
        confirmLabel="Delete link"
        message={
          <>
            <strong className="text-navy-900">{confirmDelete?.title}</strong> will be removed
            from the public page, along with its click history.
          </>
        }
        onConfirm={async () => {
          if (!confirmDelete) return;
          setIsPending(true);
          try {
            await linksApi.remove(confirmDelete.id);
            onChange(links.filter((link) => link.id !== confirmDelete.id));
            toast.success('Link deleted');
            setConfirmDelete(null);
          } catch {
            toast.error('Could not delete the link');
          } finally {
            setIsPending(false);
          }
        }}
      />
    </>
  );
}
