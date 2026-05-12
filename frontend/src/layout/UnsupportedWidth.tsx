export function UnsupportedWidth() {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-surface-overlay p-6 md:hidden">
      <div className="text-center">
        <p className="text-heading font-semibold text-text-primary">
          Minimum viewport width is 768px
        </p>
        <p className="mt-2 text-body text-text-secondary">
          Resize your browser to continue.
        </p>
      </div>
    </div>
  );
}
