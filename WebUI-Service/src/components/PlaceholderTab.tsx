type PlaceholderTabProps = {
  title: string;
  description?: string;
};

export function PlaceholderTab({ title, description }: PlaceholderTabProps) {
  return (
    <section className="panel placeholder-panel" aria-label={title}>
      <h2>{title}</h2>
      <p className="lede">{description ?? "Content coming soon."}</p>
    </section>
  );
}
