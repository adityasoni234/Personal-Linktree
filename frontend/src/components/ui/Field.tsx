import { forwardRef, useId } from 'react';
import { AlertCircle, Check } from 'lucide-react';

import { cn } from '@/lib/utils';

/* -------------------------------------------------------------------------- */
/* Field wrapper                                                              */
/* -------------------------------------------------------------------------- */

interface FieldProps {
  label?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  htmlFor?: string;
  children: React.ReactNode;
  className?: string;
  /** Rendered at the right of the label row (e.g. a character counter). */
  trailing?: React.ReactNode;
}

export function Field({
  label,
  hint,
  error,
  required,
  htmlFor,
  children,
  className,
  trailing,
}: FieldProps) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {(label || trailing) && (
        <div className="flex items-baseline justify-between gap-3">
          {label && (
            <label
              htmlFor={htmlFor}
              className="text-sm font-medium text-navy-800"
            >
              {label}
              {required && (
                <span className="ml-0.5 text-danger-600" aria-hidden="true">
                  *
                </span>
              )}
            </label>
          )}
          {trailing && <span className="text-2xs text-navy-400">{trailing}</span>}
        </div>
      )}
      {children}
      {/* Errors take precedence over hints so the row never grows on error. */}
      {error ? (
        <p className="flex items-start gap-1.5 text-sm text-danger-600" role="alert">
          <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </p>
      ) : hint ? (
        <p className="text-sm text-navy-500">{hint}</p>
      ) : null}
    </div>
  );
}

const CONTROL =
  'w-full rounded-xl border bg-white px-3.5 text-navy-900 shadow-sm transition ' +
  'placeholder:text-navy-400 ' +
  'focus:outline-none focus:ring-2 focus:ring-ieee-600/30 focus:border-ieee-600 ' +
  'disabled:cursor-not-allowed disabled:bg-navy-50 disabled:text-navy-500';

const CONTROL_ERROR =
  'border-danger-500 focus:border-danger-600 focus:ring-danger-500/25';

/* -------------------------------------------------------------------------- */
/* Input                                                                      */
/* -------------------------------------------------------------------------- */

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightSlot?: React.ReactNode;
  trailing?: React.ReactNode;
  containerClassName?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, leftIcon, rightSlot, trailing, className, containerClassName, id, ...props },
  ref,
) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const describedBy = error || hint ? `${inputId}-description` : undefined;

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      required={props.required}
      htmlFor={inputId}
      trailing={trailing}
      className={containerClassName}
    >
      <div className="relative">
        {leftIcon && (
          <span
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-navy-400"
            aria-hidden="true"
          >
            {leftIcon}
          </span>
        )}
        <input
          ref={ref}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            CONTROL,
            'h-11 border-navy-200',
            leftIcon && 'pl-10',
            rightSlot && 'pr-11',
            error && CONTROL_ERROR,
            className,
          )}
          {...props}
        />
        {rightSlot && (
          <span className="absolute right-1.5 top-1/2 -translate-y-1/2">{rightSlot}</span>
        )}
      </div>
    </Field>
  );
});

/* -------------------------------------------------------------------------- */
/* Textarea                                                                   */
/* -------------------------------------------------------------------------- */

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
  trailing?: React.ReactNode;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, trailing, className, id, rows = 3, ...props },
  ref,
) {
  const generatedId = useId();
  const textareaId = id ?? generatedId;

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      required={props.required}
      htmlFor={textareaId}
      trailing={trailing}
    >
      <textarea
        ref={ref}
        id={textareaId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        className={cn(
          CONTROL,
          'resize-y border-navy-200 py-2.5 leading-relaxed',
          error && CONTROL_ERROR,
          className,
        )}
        {...props}
      />
    </Field>
  );
});

/* -------------------------------------------------------------------------- */
/* Select                                                                     */
/* -------------------------------------------------------------------------- */

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, options, placeholder, className, id, ...props },
  ref,
) {
  const generatedId = useId();
  const selectId = id ?? generatedId;

  return (
    <Field
      label={label}
      hint={hint}
      error={error}
      required={props.required}
      htmlFor={selectId}
    >
      <select
        ref={ref}
        id={selectId}
        aria-invalid={error ? true : undefined}
        className={cn(
          CONTROL,
          'h-11 cursor-pointer appearance-none border-navy-200 pr-10',
          error && CONTROL_ERROR,
          className,
        )}
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%23526A8E' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m4 6 4 4 4-4'/%3E%3C/svg%3E\")",
          backgroundRepeat: 'no-repeat',
          backgroundPosition: 'right 0.85rem center',
        }}
        {...props}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
});

/* -------------------------------------------------------------------------- */
/* Switch                                                                     */
/* -------------------------------------------------------------------------- */

export interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
  id?: string;
}

export function Switch({ checked, onChange, label, description, disabled, id }: SwitchProps) {
  const generatedId = useId();
  const switchId = id ?? generatedId;

  return (
    <div className="flex items-start justify-between gap-4">
      <div className="min-w-0">
        <label htmlFor={switchId} className="block text-sm font-medium text-navy-800">
          {label}
        </label>
        {description && <p className="mt-0.5 text-sm text-navy-500">{description}</p>}
      </div>
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-full',
          'transition-colors focus-visible:outline-none focus-visible:ring-2',
          'focus-visible:ring-ieee-600 focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed disabled:opacity-50',
          checked ? 'bg-ieee-600' : 'bg-navy-300',
        )}
      >
        <span
          className={cn(
            'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-[1.375rem]' : 'translate-x-0.5',
          )}
        />
      </button>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Checkbox                                                                   */
/* -------------------------------------------------------------------------- */

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
  description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, description, className, id, ...props },
  ref,
) {
  const generatedId = useId();
  const checkboxId = id ?? generatedId;

  return (
    <div className={cn('flex items-start gap-3', className)}>
      <span className="relative mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center">
        <input
          ref={ref}
          id={checkboxId}
          type="checkbox"
          className="peer h-5 w-5 cursor-pointer appearance-none rounded-md border border-navy-300 bg-white transition checked:border-ieee-600 checked:bg-ieee-600 focus-visible:ring-2 focus-visible:ring-ieee-600 focus-visible:ring-offset-2"
          {...props}
        />
        <Check
          className="pointer-events-none absolute h-3.5 w-3.5 text-white opacity-0 transition-opacity peer-checked:opacity-100"
          strokeWidth={3}
          aria-hidden="true"
        />
      </span>
      <div className="min-w-0">
        <label htmlFor={checkboxId} className="cursor-pointer text-sm text-navy-800">
          {label}
        </label>
        {description && <p className="text-sm text-navy-500">{description}</p>}
      </div>
    </div>
  );
});

/* -------------------------------------------------------------------------- */
/* Colour field                                                               */
/* -------------------------------------------------------------------------- */

export interface ColorFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  disabled?: boolean;
}

export function ColorField({ label, value, onChange, hint, disabled }: ColorFieldProps) {
  const id = useId();
  const normalised = /^#[0-9a-fA-F]{6}$/.test(value) ? value : '#000000';

  return (
    <Field label={label} hint={hint} htmlFor={id}>
      <div className="flex items-center gap-2">
        <div className="relative h-11 w-12 shrink-0 overflow-hidden rounded-xl border border-navy-200 shadow-sm">
          <input
            id={id}
            type="color"
            value={normalised}
            disabled={disabled}
            onChange={(event) => onChange(event.target.value.toUpperCase())}
            className="absolute -inset-2 h-[calc(100%+1rem)] w-[calc(100%+1rem)] cursor-pointer border-0 bg-transparent p-0"
            aria-label={`${label} colour picker`}
          />
        </div>
        <input
          type="text"
          value={value}
          disabled={disabled}
          spellCheck={false}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className={cn(CONTROL, 'h-11 border-navy-200 font-mono text-sm uppercase')}
          aria-label={`${label} hex value`}
          maxLength={9}
        />
      </div>
    </Field>
  );
}

/* -------------------------------------------------------------------------- */
/* Range                                                                      */
/* -------------------------------------------------------------------------- */

export interface RangeFieldProps {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  step?: number;
  format?: (value: number) => string;
  hint?: string;
  disabled?: boolean;
}

export function RangeField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  format,
  hint,
  disabled,
}: RangeFieldProps) {
  const id = useId();
  return (
    <Field
      label={label}
      hint={hint}
      htmlFor={id}
      trailing={<span className="font-mono">{format ? format(value) : value}</span>}
    >
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 w-full cursor-pointer appearance-none rounded-full bg-navy-200 accent-ieee-600 disabled:cursor-not-allowed disabled:opacity-50"
      />
    </Field>
  );
}
