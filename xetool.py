#/bin/python3

# A lot of this code is taken from https://github.com/Free60Project/tools/blob/master/imgbuild/build.py
"""

I need to decide on the scheme for modifying data. Right now I do both inline
modifications (encrypt, decrypt, etc.) as and return the modified data

"""

import sys, struct, os
import hmac
import Crypto.Cipher.ARC4 as RC4
from hashlib import sha1 as sha

class NANDImage():

    def __init__(self, image, imagesize):
        """

        - read NAND header for SMC offset / length
        - read SMC into object
        - read SB offset from NAND header
        - read SB length from SB header
        - read SB into object
        - read SC offset / length from header
        - read SC into object
        - read SD offset / length from header
        - read SD into object
        - read SE offset / length from header
        - read SE into object
        
        """
        self.bootloaders = []

        currentoffset = 0
        MAX_READ = imagesize
        
        # Read file
        headerdata = image.read(NANDHeader.HEADER_SIZE)
        self.nandheader = NANDHeader(headerdata, currentoffset)

        # Validate image
        self.nandheader.validate()

        # read SB offset from NAND header

        currentoffset += self.nandheader.sboffset
        
        if currentoffset + Bootloader.HEADER_SIZE < MAX_READ:
            # read SB length from SB header
            image.seek(currentoffset, 0)
            sblength = Bootloader(image.read(Bootloader.HEADER_SIZE), currentoffset).length

            # read SB into object
            image.seek(currentoffset, 0)
            sbdata = image.read(sblength)
            self.sb = CB(sbdata, currentoffset)
            self.bootloaders.append(self.sb)

            currentoffset += self.sb.length

        # 3BL
        if currentoffset + Bootloader.HEADER_SIZE < MAX_READ:
            # read SC offset / length from header
            image.seek(currentoffset, 0)
            sclength = Bootloader(image.read(Bootloader.HEADER_SIZE), currentoffset).length

            # read SC into object
            image.seek(currentoffset, 0)
            ###scdata = image.read(sclength)
            scdata = image.read(Bootloader.HEADER_SIZE)
            # TODO Implement SC; however, the whole CX vs SX has to be re-thought
            self.sc = Bootloader(scdata, currentoffset)
            self.bootloaders.append(self.sc)

            currentoffset += self.sc.length


        # 4BL
        if currentoffset + Bootloader.HEADER_SIZE < MAX_READ:
            # read SD offset / length from header
            image.seek(currentoffset, 0)
            sdlength = Bootloader(image.read(Bootloader.HEADER_SIZE), currentoffset).length

            # read SD into object
            image.seek(currentoffset, 0)
            sddata = image.read(sdlength)
            self.sd = CD(sddata, currentoffset)
            self.bootloaders.append(self.sd)

            currentoffset += self.sd.length


        # 5BL
        if currentoffset + Bootloader.HEADER_SIZE < MAX_READ:
            # read SE offset / length from header
            image.seek(currentoffset, 0)
            selength = Bootloader(image.read(Bootloader.HEADER_SIZE), currentoffset).length

            # read SE into object
            image.seek(currentoffset, 0)
            sedata = image.read(selength)
            self.se = CE(sedata, currentoffset)
            self.bootloaders.append(self.se)

            currentoffset += self.se.length

    def printMetadata(self):
        print('=== ' + str(hex(self.nandheader.offset)) + ' ===\n' + str(self.nandheader))
        for bl in self.bootloaders:
            print('=== ' + str(hex(bl.offset)) + ' ===\n' + str(bl))

    def exportParts(self):

        random = bytes('\0' * 16, 'ascii')

        for bl in self.bootloaders:
            pass
            # Decrypt and export encrypted SB
            with open('output/'+bl.name+'_' + str(bl.build) + '_enc.bin', 'wb') as sbout:
                sbout.write(sb.block_encrypted)

            # Decrypt and export decrypted SB
            with open('output/SB_' + str(sb.build) + '_dec.bin', 'wb') as sbout:
                sbout.write(sb.decrypt_CB())

        sb.updateKey(random)

        # Decrypt and export decrypted SD
        with open('output/SD_' + str(sd.build) + '_enc.bin', 'wb') as sdout:
            sdout.write(sd.block_encrypted)

        # Decrypt and export decrypted SD
        with open('output/SD_' + str(sd.build) + '_dec.bin', 'wb') as sdout:
            sdout.write(sd.decrypt_CD(sb))

        sd.updateKey(sb, random)

        # Decrypt and export decrypted SE
        with open('output/SE_' + str(se.build) + '_enc.bin', 'wb') as seout:
            seout.write(se.block_encrypted)

        # Decrypt and export decrypted SE
        with open('output/SE_' + str(se.build) + '_dec.bin', 'wb') as seout:
            seout.write(se.decrypt_CE(sd))

class NANDHeader():

    HEADER_SIZE = 0x80
    MAGIC_BYTES = b'\xFF\x4F'
    MS_COPYRIGHT = b'\xa9 2004-2011 Microsoft Corporation. All rights reserved.\x00'

    def __init__(self, header, currentoffset):
        header = struct.unpack('>2s3H2I56s24s4I2H3I', header)
        self.magic = header[0]
        self.build = header[1]
        self.unknown0x4 = header[2]
        self.unknown0x6 = header[3]
        self.sboffset = header[4]
        self.cf1offset = header[5]
        self.copyright = header[6]
        self.unknown0x60 = header[8]
        self.unknown0x64 = header[9]
        self.unknown0x68 = header[10]
        self.kvoffset = header[11]
        self.metadatastyle = header[12]
        self.unknown0x72 = header[13]
        self.unknown0x74 = header[14]
        self.smclength = header[15]
        self.smcoffset = header[16]

        self.offset = currentoffset

    def __str__(self):
        ret = ''
        ret += str(self.magic)
        ret += '\n'
        ret += str(self.build)
        ret += '\n'
        ret += str(hex(self.sboffset))
        ret += '\n'
        ret += str(hex(self.cf1offset))
        ret += '\n'
        ret += str(self.copyright)
        ret += '\n'
        ret += str(hex(self.kvoffset))
        ret += '\n'
        ret += str(hex(self.metadatastyle))
        ret += '\n'
        ret += str(hex(self.smclength))
        ret += '\n'
        ret += str(hex(self.smcoffset))
        return ret

    def validate(self):
        if self.copyright[0:1]+self.copyright[11:] != NANDHeader.MS_COPYRIGHT[0:1]+NANDHeader.MS_COPYRIGHT[11:]:
            print('** Warning: failed copyright notice check invalid or custom image')

        if self.magic != NANDHeader.MAGIC_BYTES:
            print('** Failure: magic bytes check: invalid image')
            return False


class SMC():

    SMC_KEY = [0x42, 0x75, 0x4e, 0x79]
    
    def __init__(self, data, currentlocation):
        self.block_encrypted = data
        self.data = None
        
        self.offset = currentlocation

    def decrypt_SMC(self):
        res = ""
        for i in range(len(self.data)):
            j = ord(self.data[i])
            mod = j * 0xFB
            res += chr(j ^ (SMC.SMC_KEY[i&3] & 0xFF))
            SMC.SMC_KEY[(i+1)&3] += mod
            SMC.SMC_KEY[(i+2)&3] += mod >> 8
        self.data = res
        return res
    
    def encrypt_SMC(self):
        res = ""
        for i in range(len(self.data)):
            j = ord(self.data[i]) ^ (SMC.SMC_KEY[i&3] & 0xFF)
            mod = j * 0xFB
            res += chr(j)
            SMC.SMC_KEY[(i+1)&3] += mod
            SMC.SMC_KEY[(i+2)&3] += mod >> 8
        self.data = res
        return res


class Bootloader():

    HEADER_SIZE = 0x20
    SECRET_1BL = b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

    def __init__(self, header, currentlocation):
        header = struct.unpack('>2s3H2I16s', header)

        self.name = header[0]
        self.build = header[1]
        self.pairing = header[2]
        self.flags = header[3]
        self.entrypoint = header[4]
        self.length = header[5]
        self.salt = header[6]

        self.offset = currentlocation

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __repr__(self):
        return 'Bootloader({})'.format(self.data)

    def __str__(self):
        ret = ''
        ret += str(self.name)
        ret += '\n'
        ret += str(self.build)
        ret += '\n'
        ret += str(hex(self.pairing))
        ret += '\n'
        ret += str(hex(self.flags))
        ret += '\n'
        ret += str(hex(self.entrypoint))
        ret += '\n'
        ret += str(hex(self.length))
        ret += '\n'
        ret += str(self.salt)
        return ret
    
    def pack(self):
        return struct.pack('>2p3H2I16p', bytes(self.name), self.build, self.pairing, self.flags, self.entrypoint, self.length, bytes(self.salt))


class CB(Bootloader):

    def __init__(self, block_encrypted, currentlocation):
        self.block_encrypted = block_encrypted
        self.data = self.block_encrypted
        self.header = self.block_encrypted[0:Bootloader.HEADER_SIZE]
        Bootloader.__init__(self, self.header, currentlocation)
        self.key = None

    def updateKey(self, random):
        secret = Bootloader.SECRET_1BL
        self.key = hmac.new(secret, random, sha).digest()[0:0x10]

    def zeropair_CB(self):
        self.data = self.data[0:0x20] + "\0" * 0x20 + self.data[0x40:]
        return self.data

    def decrypt_CB(self):
        secret = Bootloader.SECRET_1BL
        key = hmac.new(secret, self.salt, sha).digest()[0:0x10]
        cb = self.data[0:0x10] + key + RC4.new(key).decrypt(self.data[0x20:])
        self.data = cb
        return cb

    def encrypt_CB(self, random):
        secret = SECRET_1BL
        key = hmac.new(secret, random, sha).digest()[0:0x10]
        cb = self.data[0:0x10] + random + RC4.new(key).encrypt(self.data[0x20:])
        self.data = cb
        self.key = key
        return cb, key

    
class CD(Bootloader):

    def __init__(self, block_encrypted, currentlocation):
        self.block_encrypted = block_encrypted
        self.data = self.block_encrypted
        self.header = self.block_encrypted[0:Bootloader.HEADER_SIZE]
        Bootloader.__init__(self, self.header, currentlocation)
        self.key = None

    def updateKey(self, cb, random):
        secret = cb.key
        assert secret is not None, 'No key given to updateKey'
        self.key = hmac.new(secret, random, sha).digest()[0:0x10]

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value

    def __repr__(self):
        return 'MyArray({})'.format(self.data)

    def decrypt_CD(self, cb, cpukey = None):
    # enable this code if you want to extract CD from a flash image and you know the cup key.
    # disable this when this is a zero-paired image.
    #   assert cpukey or build(CD) < 1920
        if self.build > 1920 and not cpukey:
            print('** Warning: decrypting CD > 1920 without CPU key')

        secret = cb.key
        assert secret is not None, 'No key given to decrypt_CD'

        key = hmac.new(secret, self.salt, sha).digest()[0:0x10]

        if cpukey:
            key = hmac.new(cpukey, key, sha).digest()[0:0x10]

        cd = self.data[0:0x10] + key + RC4.new(key).decrypt(self.data[0x20:])

        self.data = cd
        return cd

    def encrypt_CD(self, cb, random):
        secret = cb.key
        assert secret is not None, 'No key given to encrypt_CD'
        key = hmac.new(secret, random, sha).digest()[0:0x10]
        cd = self.data[0:0x10] + random + RC4.new(key).encrypt(self.data[0x20:])
        self.data = cd
        self.key = key
        return cd, key
    

class CE(Bootloader):

    def __init__(self, block_encrypted, currentlocation):
        self.block_encrypted = block_encrypted
        self.data = self.block_encrypted
        self.header = self.block_encrypted[0:Bootloader.HEADER_SIZE]
        Bootloader.__init__(self, self.header, currentlocation)
        self.key = None

    def decrypt_CE(self, cd):
        secret = cd.key
        assert secret is not None, 'No key given to decrypt_CE'
        key = hmac.new(secret, self.salt, sha).digest()[0:0x10]
        ce = self.data[0:0x10] + key + RC4.new(key).decrypt(self.data[0x20:])
        self.data = ce
        return ce
    
    def encrypt_CE(self, cd, random):
        secret = cd.key
        assert secret is not None, 'No key given to encrypt_CE'
        key = hmac.new(secret, random, sha).digest()[0:0x10]
        ce = self.data[0:0x10] + random + RC4.new(key).encrypt(self.data[0x20:])
        self.data = ce
        self.key = key # This is never used, storing just to be complete
        return ce


class CF(Bootloader):

    def __init__(self, block_encrypted, currentlocation):
        self.block_encrypted = block_encrypted
        self.data = self.block_encrypted
        self.header = self.block_encrypted[0:Bootloader.HEADER_SIZE]
        Bootloader.__init__(self, self.header, currentlocation)

    def zeropair_CF(self):
        self.data = self.data[0:0x21c] + "\0" * 4 + self.data[0x220:]
        return self.data

    # TODO
    """
    Need to look into these salt(?) values from the CF and CG headers
    Document CF structure as it is apparently very different
    """
    def decrypt_CF(self):
        secret = Bootloader.SECRET_1BL
        key = hmac.new(secret, self.data[0x20:0x30], sha).digest()[0:0x10]
        cf = self.data[0:0x20] + key + RC4.new(key).decrypt(self.data[0x30:])
        self.data = cf
        return cf
   
    def encrypt_CF(CF, random):
        secret = secret_1BL
        key = hmac.new(secret, random, sha).digest()[0:0x10]
        self.key = self.data[0x330:0x330+0x10]
        cf = self.data[0:0x20] + random + RC4.new(key).encrypt(self.data[0x30:])
        self.data = cf
        return cf, self.key
    
    
class CG(Bootloader):

    def __init__(self, block_encrypted, currentlocation):
        self.block_encrypted = block_encrypted
        self.data = self.block_encrypted
        self.header = self.block_encrypted[0:Bootloader.HEADER_SIZE]
        Bootloader.__init(self, self.header, currentlocation)

    def decrypt_CG(self, cf):
        secret = cf.key
        key = hmac.new(secret, CG[0x10:0x20], sha).digest()[0:0x10]
        cg = self.data[:0x10] + key + RC4.new(key).decrypt(self.data[0x20:])
        self.data = cg
        return cg
    
    def encrypt_CG(self, cf, random):
        secret = cf.key
        key = hmac.new(secret, random, sha).digest()[0:0x10]
        cg = self.data[:0x10] + random + RC4.new(key).encrypt(self.data[0x20:])
        self.data = cg
        return cg


def main(argv):
    target = argv[1] if len(sys.argv) > 1 else None

    if not target:
        sys.exit(1)

    # Parse file header
    with open(target, 'rb') as image:
        nand = NANDImage(image, os.path.getsize(target))

    nand.printMetadata()

if __name__ == '__main__':
    main(sys.argv)
