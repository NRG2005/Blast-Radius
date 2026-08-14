export default function Logo({ size = 22 }) {
  return (
    <svg
      className="brand-mark"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <g className="brand-mark-ring">
        <circle cx="12" cy="12" r="9" stroke="#ffffff22" strokeWidth="1" />
        <circle cx="12" cy="3" r="2" fill="#ee5257" />
        <circle cx="21" cy="12" r="2" fill="#f0a63e" />
        <circle cx="12" cy="21" r="2" fill="#4fa6f2" />
        <circle cx="3" cy="12" r="2" fill="#34c17e" />
      </g>
      <circle cx="12" cy="12" r="2.75" fill="#eeeef0" />
    </svg>
  );
}
