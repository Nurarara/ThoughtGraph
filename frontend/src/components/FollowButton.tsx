interface FollowButtonProps {
  following: boolean;
  onToggle: () => Promise<void>;
}

export function FollowButton({ following, onToggle }: FollowButtonProps) {
  return (
    <button className={`follow-button ${following ? "following" : ""}`} onClick={() => void onToggle()}>
      {following ? "Following" : "Follow"}
    </button>
  );
}

