export function Caveats({ items, label = "수치 시트의 주의 문구" }: { items: string[]; label?: string }) {
  if (!items.length) return null;
  return (
    <div className="caveats">
      <div>
        <strong>{label}</strong>
      </div>
      <ul>
        {items.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </div>
  );
}

export function SourceLine({ files, keys }: { files: string[]; keys: string }) {
  return (
    <p className="source-line">
      출처: results/numbers_sheet.json의 {keys}. 원파일: {files.join(", ")}
    </p>
  );
}
