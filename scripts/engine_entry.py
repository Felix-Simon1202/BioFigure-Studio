if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--image-presentation-worker']:
        from backend.image.style_queue import frozen_worker
        frozen_worker()
        sys.exit(0)
    from multiprocessing import freeze_support
    freeze_support()
    from backend.desktop.engine import main
    main()
