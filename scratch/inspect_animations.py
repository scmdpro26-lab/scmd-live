import UnityPy

def main():
    print("Loading BasicMotions.vnanim with UnityPy...")
    env = UnityPy.load("vnyan/Items/Animations/BasicMotions.vnanim")
    
    clips = []
    for obj in env.objects:
        if obj.type.name == "AnimationClip":
            data = obj.read()
            clips.append(data.m_Name)
            
    print(f"Found {len(clips)} AnimationClips:")
    for clip in sorted(set(clips)):
        print(f" - {clip}")

if __name__ == "__main__":
    main()
