document.addEventListener('DOMContentLoaded', () => {
    // ===== Reveal animations on scroll =====
    const revealElements = document.querySelectorAll('.reveal');

    revealElements.forEach((element, index) => {
        const offset = (index % 4) * 50;
        element.style.setProperty('--delay', `${offset}ms`);
    });

    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    observer.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.12 }
    );

    revealElements.forEach((element) => observer.observe(element));

    // ===== Cards grid animation on scroll =====
    const cardsGrids = document.querySelectorAll('.cards-grid-animated');
    const cardsObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('is-visible');
                    cardsObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15 }
    );
    cardsGrids.forEach((grid) => cardsObserver.observe(grid));

    // ===== Counter animation =====
    const stats = document.querySelectorAll('.stat-number');
    const animateCounter = (element) => {
        const target = Number(element.dataset.count || 0);
        const duration = 1600;
        const stepTime = 16;
        const steps = Math.max(1, Math.round(duration / stepTime));
        let currentStep = 0;

        const timer = setInterval(() => {
            currentStep += 1;
            const progress = currentStep / steps;
            // Easing function for smoother animation
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            element.textContent = String(Math.round(target * easeOutQuart));
            if (currentStep >= steps) {
                element.textContent = String(target);
                clearInterval(timer);
            }
        }, stepTime);
    };

    const statsObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting && !entry.target.dataset.animated) {
                entry.target.dataset.animated = 'true';
                animateCounter(entry.target);
            }
        });
    }, { threshold: 0.5 });

    stats.forEach((item) => statsObserver.observe(item));

    // ===== Smooth scroll for anchor links =====
    document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
        anchor.addEventListener('click', (event) => {
            const targetId = anchor.getAttribute('href');
            if (!targetId || targetId === '#') {
                return;
            }

            const target = document.querySelector(targetId);
            if (!target) {
                return;
            }

            event.preventDefault();
            const top = target.getBoundingClientRect().top + window.scrollY - 70;
            window.scrollTo({ top, behavior: 'smooth' });
        });
    });

    // ===== Parallax effects =====
    const blobs = document.querySelectorAll('.bg-blob');
    
    let ticking = false;
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                const y = window.scrollY;
                
                blobs.forEach((blob) => {
                    const speed = Number(blob.dataset.speed || 0.05);
                    blob.style.transform = `translate3d(0, ${Math.round(y * speed)}px, 0)`;
                });
                
                ticking = false;
            });
            ticking = true;
        }
    });

    // ===== FAQ accordion =====
    const faqItems = document.querySelectorAll('.faq-item');
    faqItems.forEach((item) => {
        const question = item.querySelector('.faq-question');
        if (question) {
            question.addEventListener('click', () => {
                const isActive = item.classList.contains('active');
                faqItems.forEach((faq) => faq.classList.remove('active'));
                if (!isActive) {
                    item.classList.add('active');
                }
            });
        }
    });

    // ===== 3D Tilt effect - simplified =====
    const tiltCards = document.querySelectorAll('.tilt-card');
    
    tiltCards.forEach((card) => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            
            const rotateX = (y - centerY) / 35;
            const rotateY = (centerX - x) / 35;
            
            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg)`;
            card.style.transition = 'transform 0.15s ease';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
            card.style.transition = 'transform 0.4s ease';
        });
    });

    // ===== Magnetic button effect - disabled =====

    // ===== Cursor follower - disabled =====

    // ===== Animated underline on scroll =====
    const animatedUnderlines = document.querySelectorAll('.animated-underline');
    
    const underlineObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, { threshold: 0.5 });
    
    animatedUnderlines.forEach((el) => underlineObserver.observe(el));

    // ===== Navbar scroll effect =====
    const navbar = document.querySelector('.bit-navbar');
    let lastScrollY = 0;
    
    window.addEventListener('scroll', () => {
        const currentScrollY = window.scrollY;
        
        if (navbar) {
            if (currentScrollY > 100) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
            
            // Hide/show on scroll direction
            if (currentScrollY > lastScrollY && currentScrollY > 300) {
                navbar.style.transform = 'translateY(-100%)';
            } else {
                navbar.style.transform = 'translateY(0)';
            }
        }
        
        lastScrollY = currentScrollY;
    });

    // ===== Text typing effect for hero (optional) =====
    const heroTitle = document.querySelector('.hero h1');
    if (heroTitle && heroTitle.dataset.typed === 'true') {
        const text = heroTitle.textContent;
        heroTitle.textContent = '';
        let index = 0;
        
        function typeWriter() {
            if (index < text.length) {
                heroTitle.textContent += text.charAt(index);
                index++;
                setTimeout(typeWriter, 50);
            }
        }
        typeWriter();
    }

    // ===== Floating icons random movement =====
    const floatIcons = document.querySelectorAll('.float-icon');
    
    floatIcons.forEach((icon, index) => {
        // Add slight random offset to each icon's animation
        const randomDelay = Math.random() * 2;
        const randomDuration = 3 + Math.random() * 2;
        icon.style.animationDelay = `-${randomDelay}s`;
        icon.style.animationDuration = `${randomDuration}s`;
    });

    // ===== Smooth hover for shine effect =====
    const shineElements = document.querySelectorAll('.shine-effect');
    
    shineElements.forEach((el) => {
        el.addEventListener('mouseenter', () => {
            el.style.setProperty('--shine-active', '1');
        });
    });

    // ===== Service icon pulse sync =====
    const serviceIcons = document.querySelectorAll('.service-icon');
    serviceIcons.forEach((icon, index) => {
        icon.style.animationDelay = `${index * 0.2}s`;
    });

    // ===== Morphing blob - disabled for simpler effect =====

    // ===== Process step hover effect =====
    const processSteps = document.querySelectorAll('.process-step.enhanced');
    
    processSteps.forEach((step) => {
        step.addEventListener('mouseenter', () => {
            const number = step.querySelector('.process-number');
            if (number) {
                number.style.transform = 'scale(1.15)';
                number.style.boxShadow = '0 8px 25px rgba(141, 115, 255, 0.4)';
            }
        });
        
        step.addEventListener('mouseleave', () => {
            const number = step.querySelector('.process-number');
            if (number) {
                number.style.transform = 'scale(1)';
                number.style.boxShadow = '0 4px 12px rgba(141, 115, 255, 0.3)';
            }
        });
    });

    // ===== Particles - simplified, no mouse interaction =====

    // ===== Stats number glow effect =====
    const glowNumbers = document.querySelectorAll('.stat-number.glow');
    
    glowNumbers.forEach((num) => {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    num.style.textShadow = '0 0 20px rgba(141, 115, 255, 0.5)';
                }
            });
        }, { threshold: 0.5 });
        
        observer.observe(num);
    });

    console.log('BIT Platform - All effects initialized');
});
