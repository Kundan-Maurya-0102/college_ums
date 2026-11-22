window.CNS_DATA = [
  {
    title: "Unit 1: Computer Security & Attacks",
    short: "U1: Attacks",
    badge: "vvi",
    questions: [
      {
        q: "Discuss the primary goal of computer security, and why is it important?",
        hindi: "कंप्यूटर सुरक्षा के प्राथमिक लक्ष्य पर चर्चा करें और यह महत्वपूर्ण क्यों है?",
        marks: 4,
        answer: "<p>The primary goals of computer security form the <strong>CIA Triad</strong>:</p><ul><li><strong>Confidentiality (गोपनीयता):</strong> Ensuring data is accessed only by authorized users.</li><li><strong>Integrity (अखंडता):</strong> Ensuring data is not altered or modified secretly.</li><li><strong>Availability (उपलब्धता):</strong> Ensuring system and data are available when needed by authorized users.</li></ul><p><strong>Importance:</strong> It protects sensitive data from unauthorized access, prevents financial loss, maintains system trust, and ensures business continuity against cyber threats.</p>"
      },
      {
        q: "Explain different types of cyberattack on computer systems.",
        hindi: "कंप्यूटर सिस्टम पर विभिन्न प्रकार के साइबर हमले की व्याख्या करें।",
        marks: 4,
        answer: "<p>Common types of cyber attacks include:</p><ul><li><strong>Malware (मैलवेयर):</strong> Malicious software like viruses, worms, trojans, and ransomware designed to damage or disrupt systems.</li><li><strong>Phishing (फ़िशिंग):</strong> Fraudulent communication appearing to come from a reputable source to steal sensitive data.</li><li><strong>DoS & DDoS (डोस और डीडोस):</strong> Overwhelming a network/server with traffic to make it unavailable to legitimate users.</li><li><strong>Man-in-the-Middle (MitM):</strong> Attackers intercept and alter communication between two parties.</li><li><strong>SQL Injection:</strong> Exploiting vulnerabilities to execute malicious SQL commands and access databases.</li></ul>"
      },
      {
        q: "Explain Side channel attack with examples.",
        hindi: "साइड चैनल अटैक को उदाहरण सहित समझाइये।",
        marks: 6,
        answer: "<p>A <strong>Side Channel Attack</strong> is a security exploit that attempts to extract secrets from a chip or a system by exploiting physical phenomena rather than software vulnerabilities.</p><p>Instead of trying to break the mathematical encryption, it attacks the physical implementation of the cryptosystem.</p><ul><li><strong>Timing Attack:</strong> Measures how much time computations take to leak information about the keys.</li><li><strong>Power Analysis:</strong> Monitors the power consumption of a hardware device during encryption to deduce the cryptographic key.</li><li><strong>Electromagnetic (EM) Attack:</strong> Captures and analyzes the electromagnetic radiation emitted by the device.</li><li><strong>Acoustic Analysis:</strong> Listens to the sound produced during computation (like CPU noise) to steal data.</li></ul><div class='key-point'>Example: Analyzing the power variations of a smart card while it performs AES encryption to extract the secret key.</div>"
      }
    ]
  },
  {
    title: "Unit 2: Symmetric & Asymmetric Cryptography",
    short: "U2: Cryptography",
    badge: "vvi",
    questions: [
      {
        q: "Compare between Symmetric Key Cryptography and Asymmetric Key Cryptography.",
        hindi: "सममित कुंजी क्रिप्टोग्राफी और असममित कुंजी क्रिप्टोग्राफी के बीच तुलना करें।",
        marks: 4,
        answer: "<table class='comparison-table'><tr><th>Feature</th><th>Symmetric Key (Secret Key)</th><th>Asymmetric Key (Public Key)</th></tr><tr><td><strong>Key Used</strong></td><td>Same single key is used for both encryption and decryption.</td><td>Two different keys: Public key for encryption, Private key for decryption.</td></tr><tr><td><strong>Speed</strong></td><td>Very fast execution.</td><td>Slower due to complex mathematics.</td></tr><tr><td><strong>Security Level</strong></td><td>Less secure because sharing the key is risky.</td><td>Highly secure as the private key is never shared.</td></tr><tr><td><strong>Examples</strong></td><td>DES, 3DES, AES, RC4.</td><td>RSA, DSA, Elliptic Curve (ECC).</td></tr><tr><td><strong>Usage</strong></td><td>Used for bulk data encryption.</td><td>Used for secure key exchange and digital signatures.</td></tr></table>"
      },
      {
        q: "Discuss the concept of DES and how does it work.",
        hindi: "डीईएस (DES) की अवधारणा पर चर्चा करें और यह कैसे काम करता है।",
        marks: 4,
        answer: "<p><strong>Data Encryption Standard (DES)</strong> is a symmetric-key block cipher published by NIST.</p><ul><li><strong>Block Size:</strong> It takes 64-bit blocks of plaintext.</li><li><strong>Key Size:</strong> It uses a 56-bit effective key (originally 64 bits, but 8 bits are for parity).</li><li><strong>Rounds:</strong> It performs 16 rounds of complex operations.</li></ul><p><strong>Working Principle (Feistel Network):</strong></p><ol><li><strong>Initial Permutation (IP):</strong> The 64-bit plaintext undergoes an initial rearrangement.</li><li><strong>Splitting:</strong> The block is split into Left (L0) and Right (R0) halves (32 bits each).</li><li><strong>16 Rounds:</strong> In each round, the right half is expanded, XORed with a round key, passed through S-boxes (substitution), permuted (P-box), and XORed with the left half. Then halves are swapped.</li><li><strong>Final Permutation (IP-1):</strong> After 16 rounds, the halves are joined and undergo a final permutation to produce the 64-bit ciphertext.</li></ol>"
      },
      {
        q: "Explain the purpose of the Triple DES (3DES) encryption method.",
        hindi: "ट्रिपल डीईएस (3डीईएस) एन्क्रिप्शन विधि का उद्देश्य बताएं।",
        marks: 4,
        answer: "<p><strong>Triple DES (3DES)</strong> was introduced to overcome the vulnerability of the original DES algorithm, whose 56-bit key was considered too small and susceptible to brute-force attacks.</p><p><strong>Purpose & Working:</strong></p><ul><li>It applies the DES cipher algorithm three times to each data block.</li><li><strong>Process:</strong> Ciphertext = E(K3, D(K2, E(K1, Plaintext))). It Encrypts with Key 1, Decrypts with Key 2, and Encrypts again with Key 3.</li><li><strong>Key Length:</strong> It effectively increases the key size to 112 bits or 168 bits, making it exponentially harder to break than standard DES.</li><li><strong>Transition:</strong> It served as a secure transition mechanism before the Advanced Encryption Standard (AES) was widely adopted.</li></ul>"
      },
      {
        q: "Compare AES and Rijndael in terms of their cryptographic characteristics.",
        hindi: "उनकी क्रिप्टोग्राफ़िक विशेषताओं के संदर्भ में एईएस (AES) और रिजेंडेल (Rijndael) की तुलना करें।",
        marks: 4,
        answer: "<p><strong>Rijndael</strong> is the broad cipher algorithm family, while <strong>AES</strong> is a specific, standardized version of Rijndael chosen by NIST.</p><table class='comparison-table'><tr><th>Characteristic</th><th>Rijndael</th><th>AES</th></tr><tr><td><strong>Block Size</strong></td><td>Variable: Can be 128, 160, 192, 224, or 256 bits.</td><td>Strictly fixed to <strong>128 bits</strong> only.</td></tr><tr><td><strong>Key Size</strong></td><td>Variable: Can be 128, 160, 192, 224, or 256 bits.</td><td>Fixed to <strong>128, 192, or 256 bits</strong>.</td></tr><tr><td><strong>Rounds</strong></td><td>Depends on both block size and key size.</td><td>10 (for 128-bit key), 12 (192-bit), or 14 (256-bit).</td></tr><tr><td><strong>Status</strong></td><td>The original submitted algorithm.</td><td>The US Federal Information Processing Standard (FIPS).</td></tr></table>"
      },
      {
        q: "Explain how RSA works in asymmetric-key cryptography.",
        hindi: "बताएं कि आरएसए (RSA) असममित-कुंजी क्रिप्टोग्राफी में कैसे काम करता है।",
        marks: 6,
        answer: "<p><strong>RSA (Rivest-Shamir-Adleman)</strong> is a widely used public-key cryptographic system based on the mathematical difficulty of factoring the product of two large prime numbers.</p><p><strong>Working Mechanism:</strong></p><ol><li><strong>Key Generation:</strong><ul><li>Choose two distinct, large prime numbers, <em>p</em> and <em>q</em>.</li><li>Calculate <em>n = p * q</em>. (n is the modulus for public and private keys).</li><li>Calculate Euler's totient <em>Φ(n) = (p-1)*(q-1)</em>.</li><li>Choose an integer <em>e</em> such that 1 < e < Φ(n) and e is coprime to Φ(n). (Public Key = {e, n}).</li><li>Calculate <em>d</em> (Private Key) such that <em>(d * e) mod Φ(n) = 1</em>.</li></ul></li><li><strong>Encryption:</strong> Sender uses Receiver's Public Key. Ciphertext <em>C = M<sup>e</sup> mod n</em>.</li><li><strong>Decryption:</strong> Receiver uses their own Private Key. Plaintext <em>M = C<sup>d</sup> mod n</em>.</li></ol><div class='key-point'>Security relies on the fact that while generating keys is easy, factoring <em>n</em> back into <em>p</em> and <em>q</em> to find the private key is practically impossible for large numbers.</div>"
      }
    ]
  },
  {
    title: "Unit 3: Internet & Network Security Protocols",
    short: "U3: Protocols",
    badge: "imp",
    questions: [
      {
        q: "Compare various Internet security protocols such as SSL, TLS, and IPsec.",
        hindi: "एसएसएल (SSL), टीएलएस (TLS) और आईपीसेक (IPsec) जैसे इंटरनेट सुरक्षा प्रोटोकॉल की तुलना करें और अंतर बताएं।",
        marks: 6,
        answer: "<table class='comparison-table'><tr><th>Feature</th><th>SSL (Secure Sockets Layer)</th><th>TLS (Transport Layer Security)</th><th>IPsec (Internet Protocol Security)</th></tr><tr><td><strong>OSI Layer</strong></td><td>Operates at the Transport Layer.</td><td>Operates at the Transport Layer (successor to SSL).</td><td>Operates at the Network Layer.</td></tr><tr><td><strong>Scope of Security</strong></td><td>Secures connection between a single app (e.g., browser) and a server.</td><td>Same as SSL, but more secure and modern.</td><td>Secures all traffic between two networks or hosts (Host-to-Host or Net-to-Net).</td></tr><tr><td><strong>Usage</strong></td><td>Obsolete. Web browsing, email.</td><td>Modern web browsing (HTTPS), VPNs.</td><td>Site-to-Site VPNs, securing routers.</td></tr><tr><td><strong>Authentication</strong></td><td>Uses certificates.</td><td>Uses certificates (more robust MACs).</td><td>Uses IKE (Internet Key Exchange), AH, and ESP.</td></tr></table>"
      },
      {
        q: "Elaborate the working principle of Virtual Private Network (VPN).",
        hindi: "वर्चुअल प्राइवेट नेटवर्क (VPN) के कार्य सिद्धांत को समझाइये।",
        marks: 6,
        answer: "<p>A <strong>VPN (Virtual Private Network)</strong> establishes a secure, encrypted connection over a less secure network, such as the public Internet.</p><p><strong>Working Principle:</strong></p><ol><li><strong>Tunneling:</strong> The VPN creates a virtual, secure 'tunnel' between the user's device and the VPN server. Protocols like IPsec, OpenVPN, or L2TP/IPsec are used to create this tunnel.</li><li><strong>Encryption:</strong> All data transmitted through the tunnel is encrypted. Even if an attacker intercepts the data packets, they will only see unreadable ciphertext.</li><li><strong>Encapsulation:</strong> Original data packets are wrapped (encapsulated) inside new packets with new headers. This hides the original IP addresses and routing information.</li><li><strong>Authentication:</strong> Ensures only authorized users can access the VPN (via passwords, certificates, or 2FA).</li></ol><div class='key-point'>Benefits: Bypasses geo-restrictions, provides anonymity by hiding the real IP, and secures data on public Wi-Fi.</div>"
      },
      {
        q: "Discuss the concept of digital certificates and their role in Public Key Infrastructure (PKI).",
        hindi: "डिजिटल प्रमाणपत्रों की अवधारणा और सार्वजनिक कुंजी अवसंरचना (PKI) में उनकी भूमिका पर चर्चा करें।",
        marks: 6,
        answer: "<p>A <strong>Digital Certificate</strong> is an electronic document used to prove the ownership of a public key. It functions like a digital passport.</p><ul><li>It binds a public key to an entity's identity (person, organization, server).</li><li>It is issued and cryptographically signed by a trusted third party called a <strong>Certificate Authority (CA)</strong>.</li><li>Standard format: X.509.</li></ul><p><strong>Role in PKI (Public Key Infrastructure):</strong></p><ul><li><strong>Trust Establishment:</strong> PKI provides the framework (hardware, software, policies) to manage keys and certificates. Digital certificates are the core tokens of trust in PKI.</li><li><strong>Authentication:</strong> Before establishing a secure connection (like HTTPS), a browser checks the website's digital certificate to verify it belongs to the legitimate organization.</li><li><strong>Key Distribution:</strong> They provide a safe way to distribute public keys, ensuring they haven't been tampered with by attackers (preventing Man-in-the-Middle attacks).</li></ul>"
      }
    ]
  },
  {
    title: "Unit 4: Advanced Concepts (ECC, Hashing)",
    short: "U4: Advanced",
    badge: "mod",
    questions: [
      {
        q: "Explain Elliptic curve cryptography (ECC) in detail.",
        hindi: "एलिप्टिक वक्र (Elliptic curve) क्रिप्टोग्राफी को विस्तार से समझाइए।",
        marks: 6,
        answer: "<p><strong>Elliptic Curve Cryptography (ECC)</strong> is a modern approach to public-key cryptography based on the algebraic structure of elliptic curves over finite fields.</p><p><strong>Key Details:</strong></p><ul><li><strong>Efficiency:</strong> The major advantage of ECC is that it offers equivalent security to RSA but with significantly smaller key sizes. For example, a 256-bit ECC key provides about the same security as a 3072-bit RSA key.</li><li><strong>Speed:</strong> Because the keys are smaller, ECC requires less processing power, memory, and bandwidth, making it ideal for mobile devices, smart cards, and IoT devices.</li><li><strong>The Math:</strong> It relies on the 'Elliptic Curve Discrete Logarithm Problem' (ECDLP), which is mathematically very difficult to solve. Given a point P on the curve and another point Q = k*P, it is computationally infeasible to find the scalar 'k' (the private key).</li><li><strong>Usage:</strong> Used in ECDSA (Digital Signatures) and ECDH (Key Exchange).</li></ul>"
      },
      {
        q: "Describe the purpose and operation of hashing schemes, including SHA-family.",
        hindi: "SHA-परिवार सहित हैशिंग योजनाओं के उद्देश्य और संचालन का वर्णन करें।",
        marks: 6,
        answer: "<p><strong>Hashing Schemes</strong> are one-way mathematical functions that convert an input of arbitrary length into a fixed-size string of bytes, known as a hash value or message digest.</p><p><strong>Purpose:</strong></p><ul><li><strong>Data Integrity:</strong> Any slight change in the input file drastically changes the hash output (Avalanche effect). Comparing hashes verifies if a file was altered.</li><li><strong>Password Storage:</strong> Storing password hashes instead of plain text ensures that even if a database is breached, the actual passwords remain secure.</li></ul><p><strong>Operation & SHA-Family:</strong></p><ul><li>A hash function processes the message in blocks, applying compression functions iteratively.</li><li><strong>Secure Hash Algorithm (SHA):</strong> Developed by the NSA and published by NIST.</li><li><strong>SHA-1:</strong> Produces a 160-bit hash. Now considered vulnerable to collision attacks and deprecated.</li><li><strong>SHA-2:</strong> A family including SHA-224, SHA-256, SHA-384, and SHA-512. Widely used today (e.g., in SSL/TLS, Bitcoin).</li><li><strong>SHA-3:</strong> The latest standard, based on a different internal structure (Keccak sponge function) to provide an alternative if SHA-2 is ever broken.</li></ul>"
      }
    ]
  }
];
