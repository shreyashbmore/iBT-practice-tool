export default function StartScreen({ title, directions, minutes, onStart }: {
  title: string;
  directions: string;
  minutes: number;
  onStart: () => void;
}) {
  return (
    <div className="card space-y-4">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-slate-700">{directions}</p>
      <p className="text-sm text-slate-500">Time limit: {minutes} minutes. The timer starts when you press Start.</p>
      <button className="btn-primary" onClick={onStart}>Start</button>
    </div>
  );
}
